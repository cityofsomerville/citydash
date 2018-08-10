from datetime import datetime
import os
import re
import subprocess
import utils

from dateutil.parser import parse as date_parse


class multimethod(object):
    class DispatchValueError(ValueError):
        pass

    def __init__(self, fn):
        self.default_fn = None
        self.dispatch_fn = fn
        self.table = {}

    def add(self, dispatch_val, fn=None):
        def adder(fn):
            self.table[dispatch_val] = fn
            return self

        if fn:
            adder(fn)
        else:
            return adder

    @property
    def default(self):
        def adder(fn):
            self.default_fn = fn
        return adder

    def __call__(self, *args):
        val = self.dispatch_fn(*args)

        if val in self.table:
            return self.table[val](*args)
        elif self.default_fn:
            return self.default_fn(*args)
        else:
            raise multimethod.DispatchValueError(
                "Unknown dispatch value:", val)


def extension(path, *_):
    return utils.extension(path).lower()


published_date = multimethod(extension)
published_date.default(lambda _: None)

encoding = multimethod(extension)
encoding.default(lambda _: "utf-8")

extract_text = multimethod(extension)

extract_images = multimethod(extension)

# PDF
@published_date.add("pdf")
def published_date(path):
    proc = subprocess.Popen(["pdfinfo", path],
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    out, err = proc.communicate()
    m = re.search(r"CreationDate:\s+(.*?)\n", out.decode("UTF-8"))

    if m:
        datestr = m.group(1)

        return date_parse(datestr)

    return datetime.fromtimestamp(os.path.getmtime(path))


# TODO: It may be practical to sniff pdfinfo, determine the PDF
# producer used, and make a best guess at encoding based on that
# information. We should be able to get away with using ISO-8859-9
# for now.
@encoding.add("pdf")
def encoding(_):
    return "ISO-8859-9"


@extract_text.add("pdf")
def extract_text(path, output_path):
    status = subprocess.call(["pdftotext", "-enc", encoding(path), path,
                              output_path])
    return not status
