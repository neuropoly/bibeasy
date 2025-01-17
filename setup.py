from setuptools import setup, find_packages

with open('requirements.txt') as f:
    requirements = f.readlines()

setup(
    name='bibeasy',
    version='0.2',
    author='Julien Cohen-Adad, Alexandru Foias',
    author_email='aac@example.com',
    packages=find_packages(),
    url='',
    license='LICENSE',
    description='Set of tools to manage academic bibliography, convert to CCV indexes, and other fun stuff.',
    long_description=open('README.md').read(),
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'bibeasy = bibeasy.scripts:bibeasy_cli',
        ]
    }
)
