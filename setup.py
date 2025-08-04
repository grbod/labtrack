"""Setup script for COA Management System."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="coa-management-system",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A comprehensive Certificate of Analysis management system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/COA-creator",
    packages=find_packages(include=["src", "src.*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=[
        "streamlit>=1.28.0",
        "sqlalchemy>=2.0.0",
        "alembic>=1.12.0",
        "python-docx>=1.1.0",
        "reportlab>=4.0.0",
        "watchdog>=3.0.0",
        "click>=8.1.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
        "loguru>=0.7.0",
        "pandas>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "coa-cli=src.cli:cli",
        ],
    },
)