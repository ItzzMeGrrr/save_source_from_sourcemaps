# Save source code from source maps

## Introduction

It is a python CLI tool to download source code from source maps.

## Installation

First clone this repo with:

```sh
git clone https://github.com/ItzzMeGrrr/save_source_from_sourcemaps.git
```

Navigate to the clone repo directory with:

```sh
cd save_source_from_sourcemaps
```

Install the required python packages with:

```sh
pip install -r requirements.txt
```

Now we can use the script.

## Usage

```py
usage: main.py [-h] [-o PATH] [-q] [-s] -u URL [-v]

Download code from source maps.

options:
-h, --help show this help message and exit
-o PATH, --output PATH  Output the files to given path (default=./src_<domain>)
-q, --quiet Suppress output
-s, --styles Download stylesheets (CSS) as well (default=off)
-u URL, --url URL URL of the website
-v, --verbose Print verbose output
```

## Example

Let's say for example we want to save the source code of the https://reactjs.org, we can do it with the following command:

On Windows:

```cmd
python main.py -u https://reactjs.org -o reactjs_source -s
```

On Linux:

```sh
python3 main.py -u https://reactjs.org -o reactjs_source -s
```

### What does it do?

First, it will fetch the content from the given URL with the `-u` flag.

Then, it will find all the linked JS and CSS files from the response. Fetch the contents of the found links and try to find their source map URLs.

Once the source map URLs have been found, it will fetch their content and create the directory structure and dump the file contents.
