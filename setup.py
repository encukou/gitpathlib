from setuptools import setup


with open('README.rst') as f:
    long_description = f.read()


setup(
    name='gitpathlib',
    version='0.2',
    description='Object-oriented paths in Git repositories',
    long_description=long_description,
    author='Petr Viktorin',
    author_email='encukou@gmail.com',
    keywords='git,pathlib',
    license='MIT',
    url='https://github.com/encukou/gitpathlib',
    packages=['gitpathlib'],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Libraries',
        ],
    install_requires=['pygit2'],
    zip_safe=False,
)
