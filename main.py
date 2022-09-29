import argparse
from json import JSONDecodeError
import os
import re
from urllib.parse import urlparse
import requests
from colorama import Fore
import validators
import errno

INFO = Fore.CYAN
WARN = Fore.YELLOW
ERR = Fore.RED
OUT = Fore.GREEN
RESET = Fore.RESET


parser = argparse.ArgumentParser(description="Download code from source maps.")

parser.add_argument("-u", "--url", help="URL of the site", required=True)
parser.add_argument("-q", "--quit", help="Suppress output", action="store_true")
parser.add_argument(
    "-o",
    "--output",
    help="Output the files to given path (default=src_<domain>)",
    dest="path",
)
parser.add_argument(
    "-s",
    "--styles",
    help="Download stylesheets (CSS) as well (default=off)",
    action="store_true",
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
    # TODO: also try to get all script, link tags links using bs4
    # TODO: because some links might be resource file but not have extension
    global styles
    files_list = {}
    js_files = []
    css_files = []
    for line in res.split("\n"):
        for file in re.findall('"([\-./:@a-zA-Z0-9]*\.js)"', line):
            if file not in js_files:
                js_files.append(file)
        if styles:
            for file in re.findall('"([\-./:@a-zA-Z0-9]*\.css)"', line):
                if file not in css_files:
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


def get_source_maps_list(baseurl):
    """Get sourcemap url `list` of files linked in `baseurl`'s response

    Args:
        `url` (`str`): the URL

    Returns:
        `list`: list of valid sourcemap urls
    """
    global styles
    res = requests.get(baseurl)
    files = get_all_files(res.text)
    custom_print("==== JS ====")
    found_js_sourcemaps = []
    for file in files.get("js"):
        js_file = requests.get(baseurl + file).text
        for match in re.findall("//# sourceMappingURL=(.*\.map)", js_file):
            found_js_sourcemaps.append(match)
    if styles:
        found_css_sourcemaps = []
        custom_print("==== CSS ====")
        for match in re.findall("//# sourceMappingURL=(.*\.map)", js_file):
            found_css_sourcemaps.append(match)
        return found_js_sourcemaps, found_css_sourcemaps
    return found_js_sourcemaps


def generate_output_path(url):
    """Returns path generated based on given `url`

    Args:
        `url` (`str`): the URL

    Returns:
        `str`: path name
    """
    return f"src_{urlparse(url).netloc}"


def dump_sm_json(sourcemap, out_dir):
    """Takes sourcemap json and dumps the containing files into give directory

    Args:
        `sourcemap` (`json`): sourcemap json content
        `out_dir` (`str`): output path
    """
    # TODO: parse and save sourcemap
    pass


def handle_sourcemaps(base_url, out_dir, js_sourcemaps, css_sourcemaps):
    """Takes sourcemaps list and dumps files into appropriate directory structure

    Args:
        `base_url` (`str`): the URL
        `out_dir` (`str`): the output dir
        `js_sourcemaps` (`list`): js sourcemaps list
        `css_sourcemaps` (`list`): css sourcemaps list

    Returns:
        `None`: `None`
    """
    for js_sm in js_sourcemaps:
        try:
            if not str(js_sm).startswith(
                "http"
            ):  # it might start with http when its stored on different server or something
                sm_json = requests.get(base_url + js_sm).json()
            else:
                sm_json = requests.get(js_sm).json()
            dump_sm_json(sm_json, out_dir)

        except JSONDecodeError:
            custom_print(f"'{js_sm}' does not seem to return JSON response", ERR)
    if styles:
        for css_sm in js_sourcemaps:
            try:
                if not str(css_sm).startswith(
                    "http"
                ):  # it might start with http when its stored on different server or something
                    sm_json = requests.get(base_url + css_sm).json()
                else:
                    sm_json = requests.get(css_sm).json()
                dump_sm_json(sm_json, out_dir)

            except JSONDecodeError:
                custom_print(f"'{css_sm}' does not seem to return JSON response", ERR)


if __name__ == "__main__":
    """Main function"""
    url = args.__getattribute__("url")
    quit = args.__getattribute__("quit")
    if args.__getattribute__("path"):
        output_dir = args.__getattribute__("path")
    else:
        output_dir = generate_output_path(url)

    styles = args.__getattribute__("styles")

    validate_url(url)
    validate_dir(output_dir)
    js_sourcemap = []
    css_sourcemaps = []
    if styles:
        js_sourcemap, css_sourcemaps = get_source_maps_list(url)
    else:
        js_sourcemap = get_source_maps_list(url)

    handle_sourcemaps(url, output_dir, js_sourcemap, css_sourcemaps)
    # TODO: clean up the function above
