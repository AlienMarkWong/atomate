#!/usr/bin/env python

import os

from setuptools import setup, find_packages

module_dir = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    setup(
        name='MatMethods',
        version='0.21',
        description='MatMethods has implementations of FireWorks workflows for '
                    'Materials Science',
        long_description=open(os.path.join(module_dir, 'README.rst')).read(),
        url='https://github.com/hackingmaterials/MatMethods',
        author='Anubhav Jain, Kiran Mathew',
        author_email='anubhavster@gmail.com, kmathew@lbl.gov',
        license='modified BSD',
        packages=find_packages(),
        package_data={},
        zip_safe=False,
        install_requires=['FireWorks>=1.3.3', 'pymatgen>=4.2.0',
                          'custodian>=1.0.1', 'pymatgen-db>=0.5.1',
                          'monty>=0.9.0', 'tqdm>=4.7.4', 'six'],
        extras_require={'rtransfer': ['paramiko>=1.15.0'],
                        'plotting': ['matplotlib>=1.5.2'],
                        'phonons': ['phonopy>=1.10.8']},
        classifiers=['Programming Language :: Python :: 2.7',
                     "Programming Language :: Python :: 3",
                     "Programming Language :: Python :: 3.5",
                     'Development Status :: 4 - Beta',
                     'Intended Audience :: Science/Research',
                     'Intended Audience :: System Administrators',
                     'Intended Audience :: Information Technology',
                     'Operating System :: OS Independent',
                     'Topic :: Other/Nonlisted Topic',
                     'Topic :: Scientific/Engineering'],
        test_suite='nose.collector',
        tests_require=['nose'],
        scripts=[os.path.join('scripts', f) for f in os.listdir(os.path.join(module_dir, 'scripts'))]
    )
