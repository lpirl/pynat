from os.path import join as path_join, dirname
from setuptools import setup, find_packages

version = '0.1'
README = path_join(dirname(__file__), 'README.rst')
long_description = open(README).read()
setup(
    name='pynat',
    version=version,
    description=("DNAT port forwarding in pure Python."),
    long_description=long_description,
    classifiers=[
        'Development Status :: 4 - Beta',
       'Environment :: Plugins',
       'Intended Audience :: Developers',
       'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
       'Operating System :: Unix',
       'Programming Language :: Python',
       'Topic :: Software Development :: Libraries :: Python Modules',
       'Topic :: System :: Networking',
       'Topic :: Internet'
    ],
    keywords='nat port forwarding',
    author='Lukas Pirl',
    author_email='pynat@lukas-pirl.de',
    url='https://github.com/lpirl/pynat',
    download_url='https://github.com/lpirl/pynat/tree/master',
    license='BSD',
    packages=find_packages(),
)
