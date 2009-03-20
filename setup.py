#!/usr/bin/env python

# qtestudo - unittest UI using PyQt
# Copyright (C) 2008 Florian Mayer

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import imp

def depends(deps):
    dependencies = []
    for dep in deps:
        try:
            imp.find_module(dep)
        except ImportError:
            dependencies.append(dep)
    return dependencies


try:
    # So that we can use 'develop'.
    from setuptools import setup
    SETUPTOOLS = True
except:
    # For end-users distutils is okay too.
    from distutils.core import setup
    SETUPTOOLS = False


params = dict(
    name='qtestudo',
    version='0.1.0',
    description='Graphical User Interface for the unittest framework.',
    author='Florian Mayer',
    author_email='flormayer@aim.com',
    url='http://bitbucket.org/segfaulthunter/qtestudo-mainline/',
    keywords='unittest gui ui user-interface',
    license='GPL',
    zip_safe=True,
    py_modules=['qtestudo'],
    install_requires=depends(['PyQt4']),
    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: X11 Applications :: Qt',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Testing',
    ]
)


if not SETUPTOOLS:
    del params['zip_safe']
    del params['install_requires']


if __name__ == '__main__':
    setup(**params)
