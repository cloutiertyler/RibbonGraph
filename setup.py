import os
from setuptools import setup

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='ribbon-graph',
    version='0.1',
    packages=['ribbon'],
    include_package_data=True,
    license='MIT',
    description='A Declarative Graph API Django App',
    long_description=README,
    url='https://github.com/TheArtOfEngineering/RibbonGraph',
    author='Tyler F Cloutier',
    author_email='cloutiertyler@aol.com',
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
    ],
    install_requires=[
        'py2neo',
        'djangorestframework',
    ],
)
