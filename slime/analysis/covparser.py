import os
import typing

class Coverage:
    def __init__(self, cov: typing.Union[str, dict], parser: str) -> None:
        # read and parse file if cov is a str
        if isinstance(cov, str):
            if os.path.isfile(cov):
                with open(cov, "r") as f:
                    cov = f.read()
            if parser == "lcov":
                self.cov = self._lcov_parse(cov)
        else:
            self.cov = cov
        # set methods
        self.parser = parser
        if parser == "lcov":
            self._sub = self._lcov_sub
            self._union = self._lcov_union
            self.gen = self._lcov_gen

    def __sub__(self, other):
        return self._sub(other)

    def __or__(self, other):
        return self._union(other)

    def __and__(self, other):
        """intersection"""
        return self - (self - other)


    def __xor__(self, other):
        """symmetric difference"""
        return (self | other) - (self & other)


    def write(self, file):
        cov = self.gen()
        with open(file, "w") as f:
            f.writelines(l + "\n" for l in cov)


    def _lcov_parse(self, lcov: str) -> dict:
        coverage = {}
        for source_file in lcov.strip().split("end_of_record"):
            # print(source_file)
            file_cov = {
                "lines_hit": {},
                "functions_hit": {},
                "function_names": {},
                "total_lines_found": "0",
                "total_functions_found": "0"
            }
            file_name = None
            for line in source_file.split():
                if not line:
                    continue
                method, content = line.strip().split(":", 1)
                content = content.strip()
                if method == "DA":
                    line_no, exe_count = content.split(",", 1)
                    if int(exe_count) > 0:
                        file_cov["lines_hit"][str(line_no)] = int(exe_count)
                elif method == "FNDA":
                    exe_count, func_name = content.split(",", 1)
                    if int(exe_count) > 0:
                        file_cov["functions_hit"][str(func_name)] = int(exe_count)
                elif method == "FN":
                    line_no, func_name = content.split(",", 1)
                    file_cov["function_names"][func_name] = str(line_no)
                elif method == "FNF":
                    if str(content.strip()) != "":
                        file_cov["total_functions_found"] = str(content.strip())
                elif method == "LF":
                    if str(content.strip()) != "":
                        file_cov["total_lines_found"] = str(content.strip())
                elif method == "SF":
                    file_name = content
            if file_name is not None:
                coverage[file_name] = file_cov
            else:
                if file_cov["lines_hit"] or file_cov["functions_hit"]:
                    raise Exception("lcov parse error, file name missing")
            # print(file_name)
            # print(file_cov)
            # a = input(">")
        return coverage


    def _lcov_sub(self, cov_b) -> "Coverage":
        """cov_a - cov_b"""
        cov_a = self.cov
        cov_b = cov_b.cov
        diff = {}
        for source_file in cov_a:
            if source_file in cov_b:
                diff[source_file] = {
                    "lines_hit": cov_a[source_file]["lines_hit"] - cov_b[source_file]["lines_hit"],
                    "functions_hit": cov_a[source_file]["functions_hit"] - cov_b[source_file]["functions_hit"]
                }
            else:
                diff[source_file] = {
                    "lines_hit": cov_a[source_file]["lines_hit"].copy(),
                    "functions_hit": cov_a[source_file]["functions_hit"].copy()
                }
            diff[source_file]["function_names"] = {}
            diff[source_file]["function_names"].update(cov_a[source_file]["function_names"])
            diff[source_file]["function_names"].update(cov_b[source_file]["function_names"])
            assert cov_a[source_file]["total_lines_found"] == cov_b[source_file]["total_lines_found"]
            diff[source_file]["total_lines_found"] = cov_a[source_file]["total_lines_found"]
            assert cov_a[source_file]["total_functions_found"] == cov_b[source_file]["total_functions_found"]
            diff[source_file]["total_functions_found"] = cov_a[source_file]["total_functions_found"]
        return Coverage(diff, self.parser)


    def _lcov_union(self, cov_b) -> "Coverage":
        """cov_a | cov_b"""
        cov_a = self.cov
        cov_b = cov_b.cov
        union = {}
        for source_file in cov_a.keys() | cov_b.keys():
            if source_file in cov_a and source_file in cov_b:
                union[source_file] = {
                    "lines_hit": cov_a[source_file]["lines_hit"] | cov_b[source_file]["lines_hit"],
                    "functions_hit": cov_a[source_file]["functions_hit"] | cov_b[source_file]["functions_hit"]
                }
            elif source_file in cov_a:
                union[source_file] = {
                    "lines_hit": cov_a[source_file]["lines_hit"].copy(),
                    "functions_hit": cov_a[source_file]["functions_hit"].copy()
                }
            elif source_file in cov_b:
                union[source_file] = {
                    "lines_hit": cov_b[source_file]["lines_hit"].copy(),
                    "functions_hit": cov_b[source_file]["functions_hit"].copy()
                }
            union[source_file]["function_names"] = {}
            union[source_file]["function_names"].update(cov_a[source_file]["function_names"])
            union[source_file]["function_names"].update(cov_b[source_file]["function_names"])
            assert cov_a[source_file]["total_lines_found"] == cov_b[source_file]["total_lines_found"]
            union[source_file]["total_lines_found"] = cov_a[source_file]["total_lines_found"]
            assert cov_a[source_file]["total_functions_found"] == cov_b[source_file]["total_functions_found"]
            union[source_file]["total_functions_found"] = cov_a[source_file]["total_functions_found"]
        return Coverage(union, self.parser)


    def _lcov_gen(self) -> list:
        coverage = self.cov
        lcov = ["TN:"]
        for source_file in coverage:
            lcov.append("SF:" + source_file)
            for func_name in coverage[source_file]["function_names"].keys():
                lcov.append("FN:" + coverage[source_file]["function_names"][func_name] + "," + func_name)
            for line in coverage[source_file]["functions_hit"]:
                lcov.append("FNDA:1," + str(line))
            lcov.append("FNF:" + coverage[source_file]["total_functions_found"])
            lcov.append("FNH:" + str(len(coverage[source_file]["functions_hit"])))
            for line in coverage[source_file]["lines_hit"]:
                lcov.append("DA:" + str(line) + ",1")
            lcov.append("LF:" + coverage[source_file]["total_lines_found"])
            lcov.append("LH:" + str(len(coverage[source_file]["lines_hit"])))
            lcov.append("end_of_record")
        return lcov

