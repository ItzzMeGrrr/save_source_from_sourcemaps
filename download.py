import argparse
import enum
import errno
from msilib.schema import Error
import os
from pathlib import Path
import re
from json import JSONDecodeError
from urllib.parse import urlparse

try:
    import requests
    import sourcemaps
    import validators
    from colorama import Fore
except ModuleNotFoundError as mnf:
    print(f"Module not found '{mnf.name}', please run:")
    print(f"'pip install {mnf.name}' OR 'pip install -r requirements.txt'")
    exit(1)


INFO = Fore.CYAN
WARN = Fore.YELLOW
ERR = Fore.RED
OUT = Fore.GREEN
RESET = Fore.RESET


class SOURCEMAP_TYPE(enum.Enum):
    JS = "js"
    CSS = "css"

    def all(self) -> list:
        return [self.JS, self.CSS]


class SourceMap:
    def __init__(self, base_url, path, content="", type=SOURCEMAP_TYPE.JS) -> None:
        self.base_url = base_url
        self.path = path
        self.content = content
        if not isinstance(type, SOURCEMAP_TYPE):
            raise Error(f"type has to be instance of SOURCEMAP_TYPE.")
        else:
            self.type = type

    def dump_content(outdir):
        pass

    def get_files_list() -> list:
        pass


parser = argparse.ArgumentParser(description="Download code from source maps.")

parser.add_argument(
    "-o",
    "--output",
    help="Output the files to given path (default=./src_<domain>)",
    dest="path",
)
parser.add_argument("-q", "--quit", help="Suppress output", action="store_true")
parser.add_argument(
    "-s",
    "--styles",
    help="Download stylesheets (CSS) as well (default=off)",
    action="store_true",
)
parser.add_argument("-u", "--url", help="URL of the site", required=True)
parser.add_argument("-v", "--verbose", help="Print verbose output", action="store_true")
args = parser.parse_args().__dict__


def custom_print(text, color=OUT, quit_override=False, end="\n"):
    """Print `text` with specified `color`

    Args:
        text (`str`): the text to print
        color (`color constant`, optional): color of the `text`. Defaults to `OUT`.
        quit_override (`bool`, optional): Whether to print in quit mode. Defaults to `False`.
        end (`str`, optional): end param of the print fucntion. Defaults to "`\\n`".
    """
    if not quit or quit_override:
        # TODO: fix \t issue
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
    if not dir.endswith("/"):
        dir = f"{dir}/"
        output_dir = dir
    if dir:
        if os.path.exists(dir):
            if (
                not len(os.listdir(dir)) == 0
            ):  # check whether given directory is empty or not
                custom_print(f"'{dir}' does not seem to be empty!", ERR, True)
                exit(errno.ENOTEMPTY)


def get_linked_files(base_url):
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
    res = requests.get(base_url).text
    js_files = []
    css_files = []
    if verbose:
        custom_print("==== Found JS/CSS File ====", INFO)
    for line in res.split("\n"):
        for file in re.findall('"([\-./:@a-zA-Z0-9]*\.js)"', line):
            if file not in js_files:
                if verbose:
                    custom_print(f"{file}")
                if not file.startswith("http"):
                    if file.startswith("/"):
                        if base_url.endswith("/"):
                            file = f"{base_url[:-1]}{file}"
                        else:
                            file = f"{base_url}{file}"
                    else:
                        if base_url.endswith("/"):
                            file = f"{base_url[:-1]}{file}"
                        else:
                            file = f"{base_url}{file}"
                js_files.append(file)

        if styles:
            for file in re.findall('"([\-./:@a-zA-Z0-9]*\.css)"', line):
                if file not in css_files:
                    if verbose:
                        custom_print(f"{file}")
                    if not file.startswith("http"):
                        if file.startswith("/"):
                            if base_url.endswith("/"):
                                file = f"{base_url[:-1]}{file}"
                            else:
                                file = f"{base_url}{file}"
                        else:
                            if base_url.endswith("/"):
                                file = f"{base_url[:-1]}{file}"
                            else:
                                file = f"{base_url}{file}"

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


def generate_output_path(url):
    """Returns path generated based on given `url`

    Args:
        `url` (`str`): the URL

    Returns:
        `str`: path name
    """
    return f"src_{urlparse(url).netloc}"


def get_source_maps_list(baseurl):
    """Get sourcemap url `list` of files linked in `baseurl`'s response

    Args:
        `url` (`str`): the URL

    Returns:
        `list`: list of valid sourcemap urls
    """
    global styles
    global verbose
    if verbose:
        custom_print("==== :Found JS sourcemaps: ====", INFO)
    js_sourcemap_paths = get_source_map_urls(baseurl, linked_files.get("js"), "js")
    js_sourcemap_list = []
    for sm in js_sourcemap_paths:
        js_sourcemap_list.append(SourceMap(baseurl, sm, type=SOURCEMAP_TYPE.JS))

    if styles:
        if verbose:
            custom_print("==== :Found CSS sourcemaps: ====", INFO)
        css_sourcemap_paths = get_source_map_urls(
            baseurl, linked_files.get("css"), "css"
        )
        css_sourcemap_list = []
        for sm in css_sourcemap_paths:
            css_sourcemap_list.append(SourceMap(baseurl, sm, type=SOURCEMAP_TYPE.CSS))
        return js_sourcemaps, css_sourcemap_list
    return js_sourcemap_list


if __name__ == "__main__":
    """Main function"""
    url = args.get("url")
    quit = args.get("quit")
    verbose = args.get("verbose")
    if args.get("path"):
        output_dir = args.get("path")
    else:
        output_dir = generate_output_path(url)

    styles = args.get("styles")
    if verbose:
        custom_print("Using following options: ", INFO)
        for arg in args:
            custom_print(f"{arg}: {args.get(arg)}", INFO)
    validate_url(url)
    validate_dir(output_dir)
    linked_files = get_linked_files(url)

    js_sourcemaps = []
    css_sourcemaps = []
    if styles:
        js_sourcemaps, css_sourcemaps = get_source_maps_list(url)
    else:
        js_sourcemaps = get_source_maps_list(url)

    for smp in js_sourcemaps:
        custom_print(f"{smp.base_url} {smp.path}")
    # handle_sourcemaps(url, output_dir, js_sourcemaps, css_sourcemaps)
