# vim:fileencoding=utf-8
# (c) 2011-2020 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

import logging
import subprocess
import typing

from ecleankernel.bootloader.grub import GRUB


grub2_autogen_header = '''#
# DO NOT EDIT THIS FILE
#
# It is automatically generated by '''


class GRUB2(GRUB):
    name = 'grub2'
    kernel_re = r'^\s*linux\s*(\([^)]+\))?(?P<path>\S+)'
    def_path = ('/boot/grub/grub.cfg', '/boot/grub2/grub.cfg')

    def _get_kernels(self,
                     content: str
                     ) -> typing.Iterable[str]:
        self._autogen = content.startswith(grub2_autogen_header)

        if self._autogen:
            logging.debug('Config is autogenerated, ignoring')
            return ()
        return GRUB._get_kernels(self, content)

    def has_postrm(self) -> bool:
        return self._autogen

    def postrm(self) -> None:
        if self._autogen:
            logging.debug('Calling grub2-mkconfig')
            try:
                subprocess.call(['grub-mkconfig', '-o', self.path])
                return
            except FileNotFoundError:
                pass
            subprocess.call(['grub2-mkconfig', '-o', self.path])
