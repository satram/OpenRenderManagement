from setuptools import setup, find_packages
try:
    # When using rez, "package" module is located outside the src folder.
    # It is only available for import if rez is used to resolve env.
    from package import version as puliversion
except ImportError:
    puliversion = "__PULIVERSION__"

setup(
    name='OpenRenderManagement',
    version=puliversion,
    description="Open source render farm dispatcher",
    long_description="",
    author='acs',
    author_email='opensource@mikrosimage.eu',
    license='MIT',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    zip_safe=False,
    install_requires=[
        'tornado',
        'sqlobject',
        'requests', 'simplejson',
    ],
)
