import argparse
from glob import glob
from json import JSONDecodeError
import os
import re
import requests
from colorama import Fore
import validators
import errno

INFO = Fore.CYAN
WARN = Fore.YELLOW
ERR = Fore.RED
OUT = Fore.GREEN
RESET = Fore.RESET


parser = argparse.ArgumentParser("Download code from source maps.")

parser.add_argument("-u", "--url", help="URL of the site", required=True)
parser.add_argument("-q", "--quit", help="Suppress output", action="store_true")
parser.add_argument(
    "-o", "--output", help="Output the files to given path", dest="path"
)
parser.add_argument(
    "-s", "--styles", help="Download stylesheets as well", action="store_true"
)
args = parser.parse_args()


def custom_print(text, color=OUT, quit_override=False, end="\n"):
    """Print `text` with specified `color`

    Args:
        text (`str`): the text to print
        color (`color constant`, optional): color of the `text`. Defaults to `OUT`.
        quit_override (`bool`, optional): Whether to print in quit mode. Defaults to `False`.
        end (`str`, optional): end param of the print fucntion. Defaults to "`\\n`".
    """
    if not quit or quit_override:
        if color == OUT:
            text = f"[+] {text}"
        if color == ERR:
            text = f"[-] {text}"
        if color == WARN:
            text = f"[!] {text}"
        if color == INFO:
            text = f"[i] {text}"
        print(f"{color}{text}{RESET}", end=end)


def validate_url(url):
    """Validate `url`

    Args:
        `url` (`str`): the url
    """
    if not validators.url(url):
        custom_print(f"'{url}' is not a valid url", ERR, True)
        exit(errno.EINVAL)


def validate_dir(dir):
    """validate given directory

    Args:
        `dir` (`str`): directory
    """
    if dir:
        if os.path.exists(dir):
            if (
                not len(os.listdir(dir)) == 0
            ):  # check whether given directory is empty or not
                custom_print(f"'{dir}' does not seem to be empty!", ERR, True)
                exit(errno.ENOTEMPTY)


def get_all_files(res):
    """Get js and css file dict from html response

    Args:
        `res` (`str`): html response text

    Returns:
        `dict`: js and css file dict with respective keys
    """
    # TODO: also try to get all script, link and a tags links using bs4
    # TODO: because some links might be resource file but not have extension
    global styles
    files_list = {}
    js_files = []
    css_files = []
    for line in res.split("\n"):
        for file in re.findall('"([\-./:@a-zA-Z0-9]*\.js)"', line):
            js_files.append(file)
        if styles:
            for file in re.findall('"([\-./:@a-zA-Z0-9]*\.css)"', line):
                css_files.append(file)

    if not js_files and not css_files:
        custom_print(f"No file links found in response from '{url}'", ERR, True)
        exit(errno.ENODATA)
    if styles:
        files_list = {"js": js_files, "css": css_files}
    else:
        files_list = {
            "js": js_files,
        }
    return files_list


def get_source_maps_list(url):
    """Get sourcemap url list of files linked in `url` response

    Args:
        `url` (`str`): the URL

    Returns:
        `list`: list of valid sourcemap urls
    """
    res = requests.get(url)
    files = get_all_files(res.text)
    for file in files.get("js"):
        print(file)


if __name__ == "__main__":
    """Main function"""
    url = args.__getattribute__("url")
    quit = args.__getattribute__("quit")
    output_dir = args.__getattribute__("path")
    styles = args.__getattribute__("styles")

    validate_url(url)
    validate_dir(output_dir)
    get_source_maps_list(url)
