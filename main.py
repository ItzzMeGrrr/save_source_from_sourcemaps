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
parser.add_argument("-u", "--url", help="URL of the website", required=True)
parser.add_argument("-v", "--verbose", help="Print verbose output", action="store_true")
args = parser.parse_args().__dict__


def custom_print(text, color=OUT, quit_override=False, end="\n"):
    """Print `text` with specified `color`

    Args:
        text (`str`): the text to print
        color (`const`, optional): the color of the `text`. Defaults to `OUT`.
        quit_override (`bool`, optional): Whether to print in quit mode. Defaults to `False`.
        end (`str`, optional): end param of the print function. Defaults to "`\\n`".
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
        `url` (`str`): the URL
    """
    if not validators.url(url):
        custom_print(f"'{url}' is not a valid url", ERR, True)
        exit(errno.EINVAL)


def validate_dir(dir):
    """validate given directory

    Args:
        `dir` (`str`): the to validate directory
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
    """Get JS and CSS file dict from the response

    Args:
        `res` (`str`): the HTML response

    Returns:
        `dict`: JS and CSS file dict with respective keys
    """
    # TODO: also try to get all script, link tags links using bs4
    # TODO: because some links might be resource file but not have extension
    global styles
    files_list = {}
    res = requests.get(base_url).text
    js_files = []
    css_files = []
    if verbose:
        custom_print(f"==== Found {WARN}JS{OUT}/{INFO}CSS{OUT} File ====")
    for line in res.split("\n"):
        for file in re.findall('"([\-./:@a-zA-Z0-9]*\.js)"', line):
            if file not in js_files:
                if verbose:
                    custom_print(f"{file}", WARN)
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
                        custom_print(f"{file}", INFO)
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
        `base_url` (`str`): the url
        `files` (`list`): list of file URLs, to find source maps in
        `ext` (`str`): extension of the file, to find source maps for

    Returns:
        `list`: list of found source map URLs
    """
    found_sourcemaps = {}
    for file in files:
        if verbose:
            custom_print(
                f"Finding sourcemaps in: {INFO if ext == 'css' else WARN}{file}"
            )
        file_content = requests.get(file).text
        matches = []
        for match in re.findall(
            f"//[#@] sourceMappingURL=(.*\.{ext}\.map)", file_content
        ):
            if verbose:
                custom_print(f"\tFound map: {INFO if ext == 'CSS' else WARN}{match}")
            if not file.startswith(base_url):
                url = f"http://{urlparse(file).hostname}"
            if match not in matches:
                matches.append(match)
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
        custom_print(f"==== Found {WARN}JS{OUT} sourcemaps ====")
    js_sourcemap_paths = get_source_map_urls(baseurl, files.get("js"), "js")
    js_sourcemap_list = []
    for sm in js_sourcemap_paths:
        js_sourcemap_list.append(
            SourceMap(sm, baseurl, js_sourcemap_paths.get(sm), type=SOURCEMAP_TYPE.JS)
        )

    if styles:
        if verbose:
            custom_print(f"==== Found {INFO}CSS{OUT} sourcemaps ====")
        css_sourcemap_paths = get_source_map_urls(baseurl, files.get("css"), "css")
        css_sourcemap_list = []
        for sm in css_sourcemap_paths:
            css_sourcemap_list.append(
                SourceMap(
                    sm, baseurl, css_sourcemap_paths.get(sm), type=SOURCEMAP_TYPE.CSS
                )
            )
        return js_sourcemap_list, css_sourcemap_list
    return js_sourcemap_list


def generate_output_path(url):
    """Returns path generated based on given `URL`

    Args:
        `url` (`str`): the URL

    Returns:
        `str`: path name
    """
    return f"src_{urlparse(url).netloc}"


class SourceMap:
    def __init__(
        self, file_url, base_url, path, content="", type=SOURCEMAP_TYPE.JS
    ) -> None:
        """class wrapper for handling source maps

        Args:
            `file_url` (`str`): Url of the file where this source map was found
            `base_url` (`str`): the base URL
            `path` (`str`): the path of the source map
            `content` (`JSON`, optional): source map content. Defaults to "".
            `type` (`SOURCEMAP_TYPE`, optional): type of the source map. Defaults to SOURCEMAP_TYPE.JS.

        Raises:
            Error: invalid SOURCEMAP_TYPE
        """
        self.file_url = file_url
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
        """Save files in source map content to given `out_dir`

        Args:
            out_dir (`str`): the output directory
        """
        for source in self.content:
            if verbose:
                custom_print(f"\tSaving file {source}")
            fileName = os.path.basename(source)
            path = os.path.dirname(urlparse(source).path)

            path = Path(f"{out_dir}/{path}")
            path.mkdir(parents=True, exist_ok=True)
            with open(f"{path}\{fileName}", "w", encoding="utf-8") as file:
                file.write(self.content.get(source))

    def get_proper_url(self, path):
        """Returns a valid url

        Args:
            `path` (`str`): path for which url is needed

        Returns:
            `str`: the valid URL for the `path`
        """
        if self.file_url.startswith(self.base_url):
            if self.base_url.endswith("/"):
                if path.startswith("/"):
                    req_url = f"{self.base_url[:-1]}{path}"
                else:
                    req_url = f"{self.base_url}{path}"
            else:
                if path.startswith("/"):
                    req_url = f"{self.base_url}{path}"
                else:
                    req_url = f"{self.base_url}/{path}"
        else:
            if path.startswith("/"):
                first_part = path.split("/")[1]
            else:
                first_part = path.split("/")[0]
            start_index = str(self.file_url).find(first_part)
            req_url = self.file_url[:start_index] + path

        return req_url

    def fetch_content(self):
        """Fetches content of the sourcemap and fills the `self.content`"""
        if not self.content:
            for path in self.path:
                file_path = "/".join(urlparse(self.file_url).path.split("/")[:-1])
                if path.startswith(file_path):
                    req_url = self.get_proper_url(path)
                else:
                    req_url = self.get_proper_url(f"{file_path}/{path}")
                if req_url:
                    if verbose:
                        custom_print(
                            f"Fetching... {WARN if self.type == SOURCEMAP_TYPE.JS else INFO}{req_url}"
                        )
                    res = requests.get(req_url).text
                    try:
                        self.content = sourcemaps.decode(res).sources_content
                    except JSONDecodeError as e:
                        custom_print(
                            f"'{req_url}' does not seem to return json response", ERR
                        )
                else:
                    custom_print(f"Couldn't get proper path of the sourcemap", ERR)


if __name__ == "__main__":
    """Main function"""
    url = args.get("url")
    quit_mode = args.get("quiet")
    verbose = args.get("verbose")
    styles = args.get("styles")
    if not args.get("path"):
        args["path"] = generate_output_path(url)
    output_dir = args.get("path")

    if verbose:
        custom_print("Using following options: ", INFO)
        for arg in args:
            custom_print(f"{arg}: {args.get(arg)}", INFO)

    validate_url(url)
    validate_dir(output_dir)
    js_sourcemaps = []
    css_sourcemaps = []
    if not verbose:
        custom_print("Finding sourcemaps...")
    if styles:
        js_sourcemaps, css_sourcemaps = get_source_maps_list(url)
    else:
        js_sourcemaps = get_source_maps_list(url)

    if js_sourcemaps.__len__() > 0:
        if verbose:
            custom_print(f" ==== Fetching {WARN}JS{OUT} sourcemap contents ====")
        else:
            custom_print(f"Fetching {WARN}JS{OUT} sourcemaps...")
        for js_smp in js_sourcemaps:
            js_smp.fetch_content()
        if verbose:
            custom_print(f" ==== Dumping {WARN}JS{OUT} sourcemap contents ====")
        else:
            custom_print(f"Dumping {WARN}JS{OUT} sourcemaps...")
        for js_smp in js_sourcemaps:
            js_smp.dump_content(output_dir)
    else:
        if verbose:
            custom_print(f" ==== No  {WARN}JS{ERR} sourcemaps were found! ====", ERR)
        else:
            custom_print(f"No {WARN}JS{ERR} sourcemaps were found!", ERR)
    if styles:
        if css_sourcemaps.__len__() > 0:
            if verbose:
                custom_print(f" ==== Fetching {INFO}CSS{OUT} sourcemap contents ====")
            else:
                custom_print(f"Fetching {INFO}CSS{OUT} sourcemaps...")
            for css_smp in css_sourcemaps:
                css_smp.fetch_content()
            if verbose:
                custom_print(f" ==== Dumping {INFO}CSS{OUT} sourcemap contents ====")
            else:
                custom_print(f"Dumping {INFO}CSS{OUT} sourcemaps...")
            for css_smp in css_sourcemaps:
                css_smp.dump_content(output_dir)
        else:
            if verbose:
                custom_print(
                    f" ==== No {INFO}CSS{ERR} sourcemaps were found! ====", ERR
                )
            else:
                custom_print(f"No {INFO}CSS{ERR} sourcemaps were found!", ERR)
        if os.path.exists(output_dir):
            custom_print("RESULT: Sources downloaded successfully!")
        else:
            custom_print("RESULT: Sources were not downloaded!", ERR)
