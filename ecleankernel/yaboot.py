#	vim:fileencoding=utf-8
# (c) 2011 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

import re

def get_yaboot_kernels():
	kernel_re = re.compile(r'^\s*image\s*=\s*(.+)\s*$',
			re.MULTILINE | re.IGNORECASE)

	f = open('/etc/yaboot.conf')
	for m in kernel_re.finditer(f.read()):
		yield m.group(1)
	f.close()