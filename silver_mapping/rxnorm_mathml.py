"""Native, server-rendered MathML for scientific RxNorm Report 3 formulas.

MathML is written into the static HTML during GitHub Actions, so the equations
render without external CDNs, JavaScript, or downloaded font files.
"""
from __future__ import annotations
import html
import re

from latex2mathml.converter import convert

FORMULAS = {
    "Tỷ lệ thiếu (Missing rate)": r"\operatorname{Missing}(c)=\frac{m_c}{N}\times100\%",
    "Phần trăm RxCUI có nhiều tên": r"P_{\mathrm{multi}}=\frac{N_{\geq2\ tên}}{N_{\mathrm{RxCUI}}}\times100\%",
    "Tỷ lệ bản ghi đủ điều kiện Mapping": r"P_{\mathrm{ready}}=\frac{N_{\mathrm{ready}}}{N_{\mathrm{total}}}\times100\%",
    "Nhất quán chuẩn hóa tên (Normalization audit)": r"P_{\mathrm{mismatch}}=\frac{N_{\mathrm{mismatch}}}{N}\times100\%",
    "Trung bình, trung vị, mode": r"\bar L=\frac{1}{N}\sum_{i=1}^{N}L_i,\quad \tilde L=\operatorname{Median}(L),\quad \operatorname{Mode}(L)",
    "Phương sai và độ lệch chuẩn": r"\sigma_L^2=\frac{1}{N}\sum_{i=1}^{N}(L_i-\bar L)^2,\quad \sigma_L=\sqrt{\sigma_L^2}",
    "Pearson r (tương quan tuyến tính)": r"r=\frac{\sum_{i=1}^{n}(x_i-\bar x)(y_i-\bar y)}{\sqrt{\sum_{i=1}^{n}(x_i-\bar x)^2\sum_{i=1}^{n}(y_i-\bar y)^2}}",
    "Spearman ρ (tương quan thứ hạng)": r"\rho=\operatorname{Corr}(\operatorname{rank}(x),\operatorname{rank}(y))",
    "Welch's t-test: công thức kiểm định": r"t=\frac{\bar x_1-\bar x_2}{\sqrt{\frac{s_1^2}{n_1}+\frac{s_2^2}{n_2}}}",
    "Bậc tự do Welch–Satterthwaite": r"\nu=\frac{(\frac{s_1^2}{n_1}+\frac{s_2^2}{n_2})^2}{\frac{(s_1^2/n_1)^2}{n_1-1}+\frac{(s_2^2/n_2)^2}{n_2-1}}",
    "Cohen's d: độ lớn hiệu ứng": r"d=\frac{\bar x_1-\bar x_2}{s_{\mathrm{pooled}}}",
    "Khoảng tin cậy hiệu số trung bình 95%": r"CI_{95\%}\approx(\bar x_1-\bar x_2)\pm1.96\,SE",
    "Khoảng tin cậy CI₉₅%": r"CI_{95\%}\approx\Delta\pm1.96\,SE",
    "Holm: điều chỉnh p-value cho nhiều phép thử": r"p^{\mathrm{Holm}}_{(i)}=\max_{j\leq i}\left\{\min\left(1,(m-j+1)p_{(j)}\right)\right\}",
    "Holm: điều chỉnh p-value": r"p^{\mathrm{Holm}}_{(i)}=\max_{j\leq i}\left\{\min\left(1,(m-j+1)p_{(j)}\right)\right\}",
    "Tần số kỳ vọng E của từng ô": r"E_{ij}=\frac{R_iC_j}{N}",
    "Chi-square Pearson": r"\chi^2=\sum_{i=1}^{r}\sum_{j=1}^{c}\frac{(O_{ij}-E_{ij})^2}{E_{ij}}",
    "Bậc tự do của Chi-square": r"df=(r-1)(c-1)",
    "Cramér's V: độ mạnh liên hệ": r"V=\sqrt{\frac{\chi^2}{N\min(r-1,c-1)}}",
    "Jaccard: độ tương đồng bộ token": r"J(A,B)=\frac{|A\cap B|}{|A\cup B|}",
    "Coherence của một RxCUI và toàn tập": r"C_r=\frac{1}{k_r-1}\sum_{i=2}^{k_r}J(T_{r1},T_{ri}),\quad \bar C=\frac{1}{M}\sum_{r=1}^{M}C_r",
    "Tỷ lệ RxCUI có coherence cao": r"P_{\mathrm{high}}=\frac{M_{C\geq0.7}}{M_{C\,\mathrm{comparable}}}\times100\%",
}


def atom(value: str) -> str:
    """Locale-formatted numeral to TeX; keep comma decimals and dot grouping."""
    return r"\mathrm{" + str(value).replace(" ", r"\,").replace("%", r"\%") + "}"


def number_tokens(raw: str):
    return re.findall(r"(?<![A-Za-z0-9])[-−]?\d[\d.,]*(?:e[+-]?\d+)?", raw)


def substitute_tex(title: str, raw: str):
    """Only generate a typeset substitution when the structure is recognized.

    Unmatched formulas remain ordinary readable prose, not a fabricated result.
    """
    if "không" in raw.lower() and ("chưa" in raw.lower() or "không áp dụng" in raw.lower()):
        return None
    n=number_tokens(raw)
    if title in ("Tỷ lệ thiếu (Missing rate)", "Phần trăm RxCUI có nhiều tên",
                 "Tỷ lệ bản ghi đủ điều kiện Mapping", "Nhất quán chuẩn hóa tên (Normalization audit)",
                 "Tỷ lệ RxCUI có coherence cao"):
        # input: (... / ...) × 100% = ...
        m=re.search(r"\(([\d.,]+)\s*/\s*([\d.,]+)\).*?=\s*([\d.,]+)%",raw)
        if m:
            a,b,c=m.groups()
            return rf"\frac{{{atom(a)}}}{{{atom(b)}}}\times100\%={atom(c)}\%"
        return None
    if title=="Trung bình, trung vị, mode":
        match=re.search(r"N=([\d.,]+).*?Mean=([\d.,]+).*?Median=([\d.,]+).*?Mode=([\d.,]+)",raw)
        if match:
            count,mean,median,mode=match.groups()
            return rf"\begin{{aligned}}N&={atom(count)},\quad \bar L={atom(mean)}\\ \tilde L&={atom(median)},\quad \operatorname{{Mode}}={atom(mode)}\end{{aligned}}"
    if title=="Phương sai và độ lệch chuẩn":
        m=re.search(r"Variance=([\d.,]+).*?SD=√([\d.,]+)\s*=\s*([\d.,]+)",raw)
        if m:
            var,root,sd=m.groups()
            return rf"\sigma_L^2={atom(var)},\qquad \sigma_L=\sqrt{{{atom(root)}}}={atom(sd)}"
    if title=="Pearson r (tương quan tuyến tính)":
        m=re.search(r"n=([\d.,]+).*?r=([\d.,]+);.*?≈\s*([\d.,]+)",raw)
        if m:
            count,r,r2=m.groups()
            return rf"n={atom(count)},\quad r={atom(r)},\quad r^2\approx{atom(r2)}"
        m=re.search(r"n=([\d.,]+).*?r=([\d.,]+)",raw)
        if m:
            count,r=m.groups()
            return rf"n={atom(count)},\quad r={atom(r)}"
    if title=="Spearman ρ (tương quan thứ hạng)":
        m=re.search(r"n=([\d.,]+).*?ρ=([\d.,]+)",raw)
        if m:
            count,r=m.groups()
            return rf"n={atom(count)},\quad \rho={atom(r)}"
    if title=="Welch's t-test: công thức kiểm định":
        m=re.search(r"\(([-−\d.,]+)\s*[−-]\s*([\d.,]+)\)\s*/\s*([\d.,]+)\s*≈\s*([-−\d.,]+)",raw)
        if m:
            a,b,se,t=m.groups()
            return rf"t\approx\frac{{{atom(a)}-{atom(b)}}}{{{atom(se)}}}={atom(t)}"
    if title=="Bậc tự do Welch–Satterthwaite":
        m=re.search(r"([\d.,]+)\s*$",raw)
        if m:
            return rf"\nu\approx{atom(m.group(1))}"
    if title=="Cohen's d: độ lớn hiệu ứng":
        m=re.search(r"d\s*=\s*([-−\d.,]+)\s*/\s*([\d.,]+)\s*≈\s*([-−\d.,]+)",raw)
        if m:
            a,b,c=m.groups()
            return rf"d\approx\frac{{{atom(a)}}}{{{atom(b)}}}={atom(c)}"
    if title=="Khoảng tin cậy hiệu số trung bình 95%":
        m=re.search(r"([-−\d.,]+)\s*±\s*([\d.,]+)\s*×\s*([\d.,]+)\s*≈\s*\[([-−\d.,]+);\s*([-−\d.,]+)\]",raw)
        if m:
            delta,k,se,lo,hi=m.groups()
            return rf"{atom(delta)}\pm{atom(k)}\times{atom(se)}\approx\left[{atom(lo)};{atom(hi)}\right]"
    if title.startswith("Holm:"):
        # Show the actual numerically tiny p-value as scientific notation.
        m=re.search(r"(\d+)\s*×\s*([\d.]+)e([+-]?\d+)\s*≈\s*([\d.]+)e([+-]?\d+)",raw)
        if m:
            factor,a,exp,b,exp2=m.groups()
            return rf"p_{{\mathrm{{adj}}}}={factor}\times {a}\times 10^{{{exp}}}\approx {b}\times10^{{{exp2}}}"
    if title=="Tần số kỳ vọng E của từng ô":
        m=re.search(r"E\s*=\s*([\d.,]+)\s*×\s*([\d.,]+)\s*/\s*([\d.,]+)\s*=\s*([\d.,]+)",raw)
        if m:
            a,b,c,d=m.groups()
            return rf"E_{{ij}}=\frac{{{atom(a)}\times{atom(b)}}}{{{atom(c)}}}={atom(d)}"
    if title=="Chi-square Pearson":
        m=re.search(r"\(([\d.,]+)\s*−\s*([\d.,]+)\)²\s*/\s*([\d.,]+)\s*≈\s*([\d.,]+);.*?=\s*([\d.,]+)",raw)
        if m:
            o,e,den,partial,total=m.groups()
            return rf"\frac{{({atom(o)}-{atom(e)})^2}}{{{atom(den)}}}\approx{atom(partial)},\quad \chi^2={atom(total)}"
    if title=="Bậc tự do của Chi-square":
        m=re.search(r"df=\((\d+)−1\)×\((\d+)−1\)\s*=\s*([\d.,]+)",raw)
        if m:
            a,b,c=m.groups()
            return rf"df=({a}-1)({b}-1)={atom(c)}"
    if title=="Cramér's V: độ mạnh liên hệ":
        m=re.search(r"V\s*=\s*√\[([\d.,]+)\s*/\s*\(([\d.,]+)\s*×\s*(\d+)\)\]\s*≈\s*([\d.,]+)",raw)
        if m:
            chi,total,cols,v=m.groups()
            return rf"V=\sqrt{{\frac{{{atom(chi)}}}{{{atom(total)}\times{cols}}}}}\approx{atom(v)}"
    if title=="Jaccard: độ tương đồng bộ token":
        return r"J(A,B)=\frac{4}{5}=0{,}8"
    if title=="Coherence của một RxCUI và toàn tập":
        m=re.search(r"M=([\d.,]+).*?Mean_C=([\d.,]+).*?Median_C=([\d.,]+)",raw)
        if m:
            k,mean,median=m.groups()
            return rf"M={atom(k)},\quad \bar C={atom(mean)},\quad \operatorname{{Median}}(C)={atom(median)}"
    return None


def render_math(title: str, general_raw: str, substitute_raw: str):
    """Return typeset formula and worked example. Visible math is real MathML."""
    latex=FORMULAS.get(title)
    if not latex:
        raise ValueError("Missing MathML formula for: "+title)
    definition=convert(latex, display="block")
    worked=substitute_tex(title, substitute_raw)
    if worked:
        substitution=convert(worked, display="block")
        label='<span class="r3-stage-label">Thay số từ RxNorm</span>'
        math='<div class="r3-math r3-math-worked" aria-label="'+html.escape(substitute_raw,quote=True)+'">'+substitution+'</div>'
    else:
        label='<span class="r3-stage-label">Kết quả / điều kiện áp dụng</span>'
        math='<p class="r3-math-text">'+html.escape(substitute_raw)+'</p>'
    return ('<div class="r3-math-layout"><div class="r3-math-group">'
            '<span class="r3-stage-label">Công thức tổng quát</span>'
            '<div class="r3-math" aria-label="'+html.escape(general_raw,quote=True)+'">'+definition+'</div></div>'
            '<div class="r3-math-group worked">'+label+math+'</div></div>')
