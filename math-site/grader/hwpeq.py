"""한글(HWP) 수식 스크립트 → LaTeX 변환.

한글 수식 편집기는 'a over b', 'sqrt {x}', 'LEFT ( ... RIGHT )' 같은 고유 문법을 쓴다.
흔히 쓰는 문법을 LaTeX로 옮기고, 모르는 낱말은 그대로 둔다 (원본 스크립트도 함께 보관하므로 손실 없음).
"""
import re

TOKEN = re.compile(r"\s+|<->|->|<=|>=|!=|==|\+-|-\+|<<|>>|\.\.\.|[{}#&^_~`]|[A-Za-z]+|\d+(?:\.\d+)?|[가-힣]+|.", re.S)

SYMBOLS = {
    "times": r"\times", "div": r"\div", "cdot": r"\cdot", "+-": r"\pm", "-+": r"\mp", "pm": r"\pm", "mp": r"\mp",
    "le": r"\le", "leq": r"\le", "<=": r"\le", "ge": r"\ge", "geq": r"\ge", ">=": r"\ge", "ne": r"\ne", "!=": r"\ne",
    "==": r"\equiv", "equiv": r"\equiv", "approx": r"\approx", "sim": r"\sim", "simeq": r"\simeq", "propto": r"\propto",
    "<<": r"\ll", ">>": r"\gg", "->": r"\to", "<->": r"\leftrightarrow", "rarrow": r"\rightarrow", "larrow": r"\leftarrow",
    "lrarrow": r"\leftrightarrow", "imply": r"\Rightarrow", "iff": r"\Leftrightarrow",
    "inf": r"\infty", "infinity": r"\infty", "partial": r"\partial", "nabla": r"\nabla",
    "deg": r"^{\circ}", "circ": r"\circ", "angle": r"\angle", "triangle": r"\triangle", "bot": r"\perp", "perp": r"\perp",
    "parallel": r"\parallel", "therefore": r"\therefore", "because": r"\because",
    "cdots": r"\cdots", "ldots": r"\ldots", "vdots": r"\vdots", "ddots": r"\ddots", "...": r"\cdots",
    "in": r"\in", "notin": r"\notin", "ni": r"\ni", "subset": r"\subset", "supset": r"\supset",
    "subseteq": r"\subseteq", "supseteq": r"\supseteq", "cup": r"\cup", "cap": r"\cap", "emptyset": r"\emptyset",
    "forall": r"\forall", "exist": r"\exists", "exists": r"\exists", "neg": r"\neg", "wedge": r"\wedge", "vee": r"\vee",
    "prime": "'", "odot": r"\odot", "oplus": r"\oplus", "otimes": r"\otimes", "smallsum": r"\sum",
    "sum": r"\sum", "prod": r"\prod", "int": r"\int", "iint": r"\iint", "oint": r"\oint", "lim": r"\lim",
    "sin": r"\sin", "cos": r"\cos", "tan": r"\tan", "cot": r"\cot", "sec": r"\sec", "csc": r"\csc",
    "log": r"\log", "ln": r"\ln", "exp": r"\exp", "max": r"\max", "min": r"\min", "det": r"\det", "gcd": r"\gcd",
    "lbrace": r"\{", "rbrace": r"\}", "vert": "|", "dline": r"\|", "box": r"\square", "square": r"\square",
    "star": r"\star", "bullet": r"\bullet", "dagger": r"\dagger", "hbar": r"\hbar", "ell": r"\ell",
}
GREEK = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa", "lambda", "mu",
         "nu", "xi", "omicron", "pi", "rho", "sigma", "tau", "upsilon", "phi", "chi", "psi", "omega"]
UPPER_GREEK = {"gamma", "delta", "theta", "lambda", "xi", "pi", "sigma", "upsilon", "phi", "psi", "omega"}
UNARY = {"sqrt": r"\sqrt", "bar": r"\overline", "overline": r"\overline", "under": r"\underline",
         "underline": r"\underline", "vec": r"\vec", "hat": r"\hat", "dot": r"\dot", "ddot": r"\ddot",
         "tilde": r"\tilde", "arch": r"\overset{\frown}", "acute": r"\acute", "grave": r"\grave", "check": r"\check",
         "rm": r"\mathrm", "it": "", "bold": r"\mathbf"}
MATRIX = {"matrix": "matrix", "pmatrix": "pmatrix", "bmatrix": "bmatrix", "dmatrix": "vmatrix", "cases": "cases"}
LEFT_MAP = {"(": "(", ")": ")", "[": "[", "]": "]", "{": r"\{", "}": r"\}", "|": "|", "<": r"\langle", ">": r"\rangle"}


def _tokens(script):
    return [t for t in TOKEN.findall(script) if t and not t.isspace()]


def _strip(s):
    """바깥 { } 한 겹을 벗긴다 (그 괄호가 전체를 감쌀 때만)."""
    s = s.strip()
    if s.startswith("{") and s.endswith("}"):
        depth = 0
        for i, ch in enumerate(s):
            depth += ch == "{"
            depth -= ch == "}"
            if depth == 0 and i < len(s) - 1:
                return s
        return s[1:-1]
    return s


class _P:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def group_raw(self):
        """다음 { ... } 안의 토큰을 그대로 돌려준다 ({ 가 아니면 토큰 하나)."""
        if self.peek() != "{":
            tok = self.take()
            return [tok] if tok else []
        depth, out = 0, []
        while self.peek() is not None:
            tok = self.take()
            if tok == "{":
                depth += 1
                if depth == 1:
                    continue
            elif tok == "}":
                depth -= 1
                if depth == 0:
                    break
            out.append(tok)
        return out

    def scripted_atom(self):
        value = self.atom()
        while self.peek() in ("^", "_"):
            value += self.atom()
        return value

    def atom(self):
        tok = self.take()
        if tok is None:
            return ""
        low = tok.lower()
        if tok == "{":
            self.i -= 1
            return "{" + convert_tokens(self.group_raw()) + "}"
        if low in UNARY:
            arg = _strip(self.atom())
            cmd = UNARY[low]
            return arg if not cmd else f"{cmd}{{{arg}}}"
        if low == "root":
            n = _strip(self.atom())
            if (self.peek() or "").lower() == "of":
                self.take()
            return rf"\sqrt[{n}]{{{_strip(self.atom())}}}"
        if low in MATRIX:
            env = MATRIX[low]
            return rf"\begin{{{env}}}{convert_tokens(self.group_raw())}\end{{{env}}}"
        if low in ("left", "right"):
            nxt = self.take() or "."
            return ("\\left" if low == "left" else "\\right") + LEFT_MAP.get(nxt, nxt)
        if tok in ("^", "_"):
            return tok + "{" + _strip(self.atom()) + "}"
        if tok == "~":
            return r"\ "
        if tok == "`":
            return r"\,"
        if low in GREEK:
            upper = tok.isupper() and low in UPPER_GREEK
            return "\\" + (low.capitalize() if upper else low) + " "
        if low in SYMBOLS or tok in SYMBOLS:
            sym = SYMBOLS.get(low, SYMBOLS.get(tok))
            return sym + (" " if sym.startswith("\\") else "")
        if re.fullmatch(r"[가-힣]+", tok):
            return rf"\text{{{tok}}}"
        if tok == "}":
            return r"\}"
        return tok


def convert_tokens(toks):
    p = _P(toks)
    items = []
    while p.peek() is not None:
        tok = p.peek()
        if tok.lower() == "over":  # 바로 앞뒤 덩어리를 분수로
            p.take()
            left = items.pop() if items else ""
            items.append(rf"\frac{{{_strip(left)}}}{{{_strip(p.scripted_atom())}}}")
        elif tok in ("#", "&"):
            p.take()
            items.append(r" \\ " if tok == "#" else " & ")
        else:
            items.append(p.scripted_atom())
    return re.sub(r" +", " ", "".join(items)).strip()


def hwp_to_latex(script: str) -> str:
    try:
        return convert_tokens(_tokens(script or ""))
    except Exception:
        return script or ""
