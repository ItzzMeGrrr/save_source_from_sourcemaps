import argparse
from colorama import Fore


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

args = parser.parse_args()

url = args.__getattribute__("url")
quit = args.__getattribute__("quit")
output_dir = args.__getattribute__("path")


def custom_print(text, color=OUT, quit_override=False, end="\n"):
    if not quit or quit_override:
        print(f"{color}{text}{RESET}", end=end)


