import setuptools

with open("README.md", "r") as f:
    long_description = f.read()

setuptools.setup(
    name="SLIME",
    version="0.9.7",
    description="I'm not a bad slime!",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/elesiuta/",
    packages=['slime', 'slime.analysis'],
    entry_points={
        'console_scripts': [
            'slime = slime.cli:main',
            'slime.diff = slime.analysis.statediff:main',
            'slime.fsmproduct = slime.analysis.comparestatemachines:main',
            'slime.label = slime.analysis.consistentlabeler:main',
            'slime.legend = slime.analysis.prettylabels:main',
            'slime.logck = slime.analysis.logchecker:main',
            'slime.logcleaner = slime.analysis.logpicklecleaner:main',
            'slime.msgexamples = slime.analysis.msgexamples:main',
            'slime.pretty = slime.analysis.dotcleaner:main',
            'slime.states = slime.analysis.staterenamer:main',
            'slime.trace = slime.analysis.statetrace:main',
            'slime.trace_stats = slime.analysis.trace_stats:main',
        ]
    },
    install_requires=["mitmproxy==8.1.0", "pika==1.2.1", "psutil", "xmltodict==0.13.0", "loguru", "flask==2.1.1", "werkzeug==2.1.1"],
    classifiers=[
        "Programming Language :: Python :: 3",
    ],
)
