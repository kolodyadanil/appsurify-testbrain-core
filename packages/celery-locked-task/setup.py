from setuptools import setup, find_packages

setup(
    name='celery-locked-task',
    version='0.1.3-dev1',
    description='Prevent duplicate celery tasks',
    author='',
    author_email='',
    url='',
    license='MIT',
    install_requires=[
        'celery>=4.0.0',
        'redis>=2.10.5',
    ],
    packages=find_packages('.')
)
