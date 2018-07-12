from setuptools import setup

setup(
    name='remotepy',
    version='0.1',
    py_modules=['remote'],
    install_requires=[
        'Click',
        'paramiko'
    ],
    entry_points={
        'console_scripts': ['remotepy=remote:main']
    }
)
