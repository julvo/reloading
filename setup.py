from distutils.core import setup

setup(
  name = 'reloading',         
  packages = ['reloading'],   
  version = '1.0.1',      
  license='MIT',        
  description = 'Reloads source code of a running program without losing state',
  author = 'Julian Vossen',
  author_email = 'pypi@julianvossen.de',
  url = 'https://github.com/julvo/reloading',
  download_url = 'https://github.com/julvo/reloading/archive/v1.0.1.tar.gz',
  keywords = ['reload', 'reloading', 'refresh', 'loop', 'decorator'],
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
  ],
)
