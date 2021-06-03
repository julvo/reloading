from setuptools import setup
from os import path

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
  name='reloading',         
  packages=['reloading'],   
  version='1.1.1',      
  license='MIT',        
  description='Reloads source code of a running program without losing state',
  long_description=long_description,
  long_description_content_type='text/markdown',
  author='Julian Vossen',
  author_email='pypi@julianvossen.de',
  url='https://github.com/julvo/reloading',
  download_url='https://github.com/julvo/reloading/archive/v1.1.1.tar.gz',
  keywords=['reload', 'reloading', 'refresh', 'loop', 'decorator'],
  install_requires=[],
  classifiers=[
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'Topic :: Utilities',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.4',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
    'Programming Language :: Python :: 3.9',
  ],
)
