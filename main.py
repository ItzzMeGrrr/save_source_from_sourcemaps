import argparse
from email.mime import base
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


parser = argparse.ArgumentParser(description="Download code from source maps.")

parser.add_argument(
    "-o",
    "--output",
    help="Output the files to given path (default=./src_<domain>)",
    dest="path",
)
parser.add_argument("-q", "--quiet", help="Suppress output", action="store_true")
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
    global quit_mode
    if not quit_mode or quit_override:
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


def get_all_files(base_url):
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
        custom_print(f"No file links found in response from '{base_url}'", ERR, True)
        exit(errno.ENODATA)
    if styles:
        files_list = {"js": js_files, "css": css_files}
    else:
        files_list = {
            "js": js_files,
        }
    return files_list


def get_source_map_urls(base_url, files, ext):
    """return all sourcemap urls from `files` of type `ext`

    Args:
        base_url (`str`): the url
        files (`list`): list of file url to find sourcemap in
        ext (`str`): extension of the file to find sourcemap for

    Returns:
        `list`: list of found sourcemap urls
    """
    found_sourcemaps = {}
    for file in files:
        if verbose:
            custom_print(f"Finding sourcemaps in: {file}", INFO)
        file_content = requests.get(file).text
        matches = []
        for match in re.findall(
            f"//[#@] sourceMappingURL=(.*\.{ext}\.map)", file_content
        ):
            if verbose:
                custom_print(f"\tFound map: {match}")
            url = base_url
            if not file.startswith(base_url):
                # TODO: fix this file on different server issue
                url = f"http://{urlparse(file).hostname}"
                # TODO: determine path of the file dynamically and append found sourcemap url to the base url
            matches.append(match)
            """if not match.startswith("http"):
                if match.startswith("/"):
                    if url.endswith("/"):
                        match = f"{url[:-1]}{match}"
                    else:
                        match = f"{url}{match}"
                else:
                    if url.endswith("/"):
                        match = f"{url}{match}"
                    else:
                        match = f"{url}/{match}" """
        found_sourcemaps[file] = matches
    return found_sourcemaps


def get_source_maps_list(baseurl):
    """Get sourcemap url `list` of files linked in `baseurl`'s response

    Args:
        `url` (`str`): the URL

    Returns:
        `list`: list of valid sourcemap urls
    """
    global styles
    global verbose
    files = get_all_files(baseurl)
    if verbose:
        custom_print("==== Found JS sourcemaps ====", INFO)
    js_sourcemap_paths = get_source_map_urls(baseurl, files.get("js"), "js")
    js_sourcemap_list = []
    for sm in js_sourcemap_paths:
        js_sourcemap_list.append(
            SourceMap(sm, js_sourcemap_paths.get(sm), type=SOURCEMAP_TYPE.JS)
        )

    if styles:
        if verbose:
            custom_print("==== Found CSS sourcemaps ====", INFO)
        css_sourcemap_paths = get_source_map_urls(baseurl, files.get("css"), "css")
        css_sourcemap_list = []
        for sm in css_sourcemap_paths:
            css_sourcemap_list.append(
                SourceMap(sm, js_sourcemap_paths.get(sm), type=SOURCEMAP_TYPE.CSS)
            )
        return js_sourcemap_list, css_sourcemap_list
    return js_sourcemap_list


def generate_output_path(url):
    """Returns path generated based on given `url`

    Args:
        `url` (`str`): the URL

    Returns:
        `str`: path name
    """
    return f"src_{urlparse(url).netloc}"


def get_json_res(sm_path, base_url):
    """fetches and returns json response from `sm_path`

    Args:
        `sm_path` (`str`): path/url to sourcemap
        `base_url` (`str`): the base url

    Returns:
        `json`: json content from `sm_path`
    """
    if not str(sm_path).startswith(
        "http"
    ):  # it might start with http when its not relative path (not stored on the same server)
        custom_print(f"{sm_path}, {base_url}", ERR)
        res = requests.get(base_url + sm_path)
        res.json()
        sm_json = res.text
    else:
        res = requests.get(sm_path)
        res.json()
        sm_json = res.text
    return sm_json


def dump_sm_json(sm, out_dir):
    """Takes sourcemap json and dumps the containing files into given directory

    Args:
        `sourcemap` (`json`): sourcemap json content
        `out_dir` (`str`): output path
    """
    source_content = sourcemaps.decode(sm).sources_content
    for source in source_content:
        if verbose:
            custom_print(f"\tSaving file {source}")
        path = os.path.dirname(str(source).replace(":///", "/").replace("/./", "/"))
        fileName = os.path.basename(path)

        path = Path(f"{out_dir}{path}")
        path.mkdir(parents=True, exist_ok=True)

        with open(rf"{path}{fileName}", "w") as file:
            file.write(str(source_content.get(source), encoding="utf-8"))


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
            sm_json = get_json_res(js_sm, base_url)
            if verbose:
                custom_print(f"===== Dumping {js_sm} =====")
            dump_sm_json(sm_json, out_dir)
        except JSONDecodeError:
            custom_print(f"'{js_sm}' does not seem to return JSON response", ERR)
    if styles:
        for css_sm in css_sourcemaps:
            try:
                sm_json = get_json_res(css_sm, base_url)
                if verbose:
                    custom_print(f"===== Dumping {css_sm} =====")
                dump_sm_json(sm_json, out_dir)
            except JSONDecodeError:
                custom_print(f"'{css_sm}' does not seem to return JSON response", ERR)


class SourceMap:
    def __init__(self, base_url, path, content="", type=SOURCEMAP_TYPE.JS) -> None:
        self.base_url = base_url
        self.path = path
        self.content = content
        if not isinstance(type, SOURCEMAP_TYPE):
            raise Error(
                f"type has to be instance of SOURCEMAP_TYPE.",
            )
        else:
            self.type = type

    def dump_content(self, out_dir):
        for source in self.content:
            if verbose:
                custom_print(f"\tSaving file {source}")
            path = os.path.dirname(str(source).replace(":///", "/").replace("/./", "/"))
            fileName = os.path.basename(path)

            path = Path(f"{out_dir}{path}")
            path.mkdir(parents=True, exist_ok=True)

            with open(rf"{path}{fileName}", "w") as file:
                file.write(str(self.content.get(source)))

    def get_file_list() -> list:
        # return files list in the content of the sourcemap
        pass

    def fetch_content(self, base_url) -> bool:
        if not self.content:
            req_url = ""
            for path in self.path:
                if self.base_url.startswith(base_url):
                    if base_url.endswith("/"):
                        if path.startswith("/"):
                            req_url = f"{base_url[:-1]}{path}"
                        else:
                            req_url = f"{base_url}{path}"
                    else:
                        if path.startswith("/"):
                            req_url = f"{base_url}{path}"
                        else:
                            req_url = f"{base_url}/{path}"

                else:
                    # TODO: determine url
                    continue
                if req_url:
                    custom_print(f"fetching... {req_url}")
                    res = requests.get(req_url).text
                    self.content = sourcemaps.decode(res).sources_content


if __name__ == "__main__":
    """Main function"""
    url = args.get("url")
    quit_mode = args.get("quiet")
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
    js_sourcemaps = []
    css_sourcemaps = []
    if styles:
        js_sourcemaps, css_sourcemaps = get_source_maps_list(url)
    else:
        js_sourcemaps = get_source_maps_list(url)

    if verbose:
        custom_print(" ==== Fetching sourcemap contents ====")
    for js_smp in js_sourcemaps:
        js_smp.fetch_content(url)
    if verbose:
        custom_print(" ==== Dumping sourcemap contents ====")
    for js_smp in js_sourcemaps:
        js_smp.dump_content(output_dir)

    # for smp in js_sourcemaps:
    #     custom_print(f"{smp.base_url}")
    #     for path in smp.path:
    #         custom_print(f"\t{path}", INFO)

    # handle_sourcemaps(url, output_dir, js_sourcemaps, css_sourcemaps)
