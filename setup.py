# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(
    name='euchre-plt',
    version='',
    packages=find_packages(include=['euchplt']),
    url='',
    license='',
    author='crash',
    author_email='',
    description='',
    install_requires=['pyyaml'],
    entry_points={
        'console_scripts': [
            'deal = euchplt.deal:main',
            'game = euchplt.game:main',
            'match = euchplt.match:main',
            'strategy = euchplt.strategy.__main__:main',
            'tournament = euchplt.tournament:main',
            'bid_data = ml.bid_data:main',
            'play_data = ml.play_data:main'
        ],
    }
)
