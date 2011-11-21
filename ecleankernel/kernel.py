#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

import os, os.path, shutil, struct

from collections import defaultdict
from functools import partial
from glob import glob

class PathRef(str):
	def __init__(self, path):
		str.__init__(self, path)
		self._refs = 0

	def ref(self):
		self._refs += 1

	def unref(self):
		self._refs -= 1
		if not self._refs:
			print('- %s' % self)
			if os.path.isdir(self):
				shutil.rmtree(self)
			else:
				os.unlink(self)

def OnceProperty(f):
	def _get(propname, self):
		try:
			return getattr(self, propname)
		except AttributeError:
			return None

	def _set(propname, self, val):
		if hasattr(self, propname):
			raise KeyError('Value for %s already set' % propname)
		val.ref()
		return setattr(self, propname, val)

	def _del(propname, self):
		if hasattr(self, propname):
			getattr(self, propname).unref()

	attrname = '_%s' % f.__name__
	funcs = [partial(x, attrname) for x in (_get, _set, _del)]
	return property(*funcs)

class Kernel(object):
	""" An object representing a single kernel version. """

	def __init__(self, version):
		self._version = version

	@property
	def version(self):
		return self._version

	@OnceProperty
	def vmlinuz(self):
		pass

	@OnceProperty
	def systemmap(self):
		pass

	@OnceProperty
	def config(self):
		pass

	@OnceProperty
	def modules(self):
		pass

	@OnceProperty
	def build(self):
		pass

	@OnceProperty
	def initramfs(self):
		pass

	parts = ('vmlinuz', 'systemmap', 'config', 'initramfs',
			'modules', 'build')

	@property
	def mtime(self):
		# prefer vmlinuz, fallback to anything
		# XXX: or maybe max()? min()?
		for p in self.parts:
			path = getattr(self, p)
			if path is not None:
				return os.path.getmtime(path)

	def unrefall(self):
		del self.vmlinuz
		del self.systemmap
		del self.config
		del self.initramfs
		del self.modules
		del self.build

	def check_writable(self):
		for path in (self.vmlinuz, self.systemmap, self.config,
				self.initramfs, self.modules, self.build):
			if path and not os.access(path, os.W_OK):
				raise OSError('%s not writable, refusing to proceed' % path)

	def __repr__(self):
		return "Kernel(%s, '%s%s%s%s%s')" % (repr(self.version),
				'V' if self.vmlinuz else ' ',
				'S' if self.systemmap else ' ',
				'C' if self.config else ' ',
				'I' if self.initramfs else ' ',
				'M' if self.modules else ' ',
				'B' if self.build else ' ')

class PathDict(defaultdict):
	def __contains__(self, path):
		path = os.path.realpath(path)
		return defaultdict.__contains__(self, path)

	def __missing__(self, path):
		path = os.path.realpath(path)

		if not defaultdict.__contains__(self, path):
			self[path] = PathRef(path)
		return self[path]

class KernelDict(defaultdict):
	def __missing__(self, kv):
		k = Kernel(kv)
		self[kv] = k
		return k

	def __delitem__(self, kv):
		if kv not in self:
			raise KeyError(kv)
		self[kv].unrefall()
		defaultdict.__delitem__(self, kv)

	def __iter__(self):
		return iter(self.values())

	def __repr__(self):
		return 'KernelDict(%s)' % ','.join(['\n\t%s' % repr(x) for x in self.values()])

def get_real_kv(path):
	f = open(path, 'rb')
	f.seek(0x200)
	buf = f.read(0x10)
	if buf[2:6] != b'HdrS':
		raise NotImplementedError('Invalid magic for kernel file (!= HdrS)')
	offset = struct.unpack_from('H', buf, 0x0e)[0]
	f.seek(offset - 0x10, 1)
	buf = f.read(0x100) # XXX
	return str(buf.split(b' ', 1)[0])

def find_kernels(exclusions = ()):
	""" Find all files and directories related to installed kernels. """

	globs = (
		('vmlinuz', '/boot/vmlinuz-'),
		('vmlinuz', '/boot/vmlinux-'),
		('vmlinuz', '/boot/kernel-'),
		('vmlinuz', '/boot/bzImage-'),
		('systemmap', '/boot/System.map-'),
		('config', '/boot/config-'),
		('initramfs', '/boot/initramfs-'),
		('initramfs', '/boot/initrd-'),
		('modules', '/lib/modules/')
	)

	# paths can repeat, so keep them sorted
	paths = PathDict()

	kernels = KernelDict()
	for cat, g in globs:
		if cat in exclusions:
			continue
		for m in glob('%s*' % g):
			kv = m[len(g):]
			if cat == 'initramfs' and kv.endswith('.img'):
				kv = kv[:-4]
			elif cat == 'modules' and m in paths:
				continue

			path = paths[m]
			newk = kernels[kv]
			try:
				setattr(newk, cat, path)
			except KeyError:
				raise SystemError('Colliding %s files: %s and %s'
						% (cat, m, getattr(newk, cat)))

			if cat == 'modules':
				builddir = paths[os.path.join(path, 'build')]
				if os.path.isdir(builddir):
					newk.build = builddir

				if '%s.old' % kv in kernels:
					kernels['%s.old' % kv].modules = path
					if newk.build:
						kernels['%s.old' % kv].build = builddir
			if cat == 'vmlinuz':
				realkv = get_real_kv(path)
				moduledir = os.path.join('/lib/modules', realkv)
				builddir = paths[os.path.join(moduledir, 'build')]
				if 'modules' not in exclusions and os.path.isdir(moduledir):
					newk.modules = paths[moduledir]
				if 'build' not in exclusions and os.path.isdir(builddir):
					newk.build = paths[builddir]

	# fill .old files
	for k in kernels:
		if '%s.old' % k.version in kernels:
			oldk = kernels['%s.old' % k.version]
			# it seems that these are renamed .old sometimes
			if not oldk.systemmap and k.systemmap:
				oldk.systemmap = k.systemmap
			if not oldk.config and k.config:
				oldk.config = k.config

	return kernels
