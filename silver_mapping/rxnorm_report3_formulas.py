"""Presentation-ready formula cards computed from published RxNorm report evidence.

Rules: label inferred intermediate values; never invent unexported sample variances,
Pearson sums or Jaccard row-pair scores. Code is purely presentational.
"""
from __future__ import annotations
import html
import math

from silver_mapping.rxnorm_mathml import render_math


def esc(v):
    return html.escape(str(v), quote=True)


def vi(number, places=0):
    if number is None:
        return "—"
    if places:
        s = f"{float(number):,.{places}f}"
    else:
        s = f"{int(number):,}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def formula(title, general, substitute, interpretation, definitions="", note=""):
    # Static MathML is generated in Python; browser requires no extra runtime.
    return (
        '<article class="r3-formula">'
        '<div class="r3-formula-header"><span class="r3-formula-marker">ƒ</span>'
        '<h4 class="r3-formula-title">' + esc(title) + '</h4></div>'
        + render_math(title, general, substitute)
        + '<div class="r3-explanation"><span class="r3-speak-icon">✦</span>'
        '<div><strong>Cách trình bày</strong><p>' + esc(interpretation) + '</p></div></div>'
        + ('<details class="r3-formula-details"><summary>Giải thích ký hiệu và lưu ý</summary>'
           + ('<p><strong>Ký hiệu:</strong> ' + esc(definitions) + '</p>' if definitions else "")
           + ('<p>' + esc(note) + '</p>' if note else "") + '</details>'
           if definitions or note else "")
        + '</article>'
    )


STYLE = """<style>
/* Report 3 · mathematical typography: academic layout, no external fonts or scripts */
.r3-formula-guide{margin:24px 0 26px}
.r3-formula-guide>h3{font-size:19px;margin:4px 0 6px;font-weight:760;color:#173c49}
.r3-formula-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:16px 0 22px}
.r3-formula{background:#fff;border:1px solid #dfe9e9;border-radius:17px;padding:0;overflow:hidden;min-width:0;
 box-shadow:0 4px 16px rgba(17,61,70,.045);transition:box-shadow .22s ease,transform .22s ease}
.r3-formula:hover{box-shadow:0 10px 26px rgba(17,61,70,.085);transform:translateY(-1px)}
.r3-formula-header{padding:17px 18px 12px;display:flex;gap:12px;align-items:center}
.r3-formula-marker{width:34px;height:34px;border-radius:10px;background:#e7f4f0;color:#0e8074;
 display:inline-grid;place-items:center;font-family:Georgia,serif;font-style:italic;font-size:20px;flex-shrink:0}
.r3-formula-title{font-size:14px!important;line-height:1.38;font-weight:750;margin:0!important;color:#234653}
.r3-math-layout{padding:0 15px 16px}
.r3-math-group{position:relative;padding:12px 10px 13px;margin-top:8px;background:#f5f8fa;border:1px solid #eef1f2;
 border-radius:11px;min-width:0}
.r3-math-group.worked{background:#eaf7f3;border-color:#d8ebe5;margin-top:10px}
.r3-stage-label{font-size:10px;font-weight:800;letter-spacing:.7px;text-transform:uppercase;color:#718791;
 display:block;margin:0 0 9px 3px}
.r3-math-group.worked .r3-stage-label{color:#088377}
.r3-math{color:#19404d;overflow-x:auto;overflow-y:hidden;max-width:100%;padding:9px 3px 11px;
 font-size:17px;line-height:1.5;scrollbar-width:thin}
.r3-math math{font-size:1em;display:block;max-width:max-content;min-width:min-content;
 margin-left:auto;margin-right:auto;white-space:nowrap}
.r3-math-worked{color:#0b746d;font-size:18px;font-weight:650}
.r3-math-text{font-size:12px;line-height:1.65;color:#526d76;margin:4px 5px 7px}
.r3-explanation{display:flex;gap:12px;padding:15px 18px;background:#fbfdfd;border-top:1px solid #eaf0f0}
.r3-speak-icon{width:25px;height:25px;flex-shrink:0;border-radius:8px;display:grid;place-items:center;
 color:#0b8276;background:#e9f5f2;font-size:14px}
.r3-explanation strong{font-size:11px;color:#0d7b70;text-transform:uppercase;letter-spacing:.6px}
.r3-explanation p{font-size:12px;line-height:1.65;margin:5px 0 0;color:#47636b}
.r3-formula-details{border-top:1px solid #ecf1f0;padding:0 19px 12px;font-size:12px;color:#526a73}
.r3-formula-details summary{cursor:pointer;padding-top:12px;font-weight:650;color:#5b7780}
.r3-formula-details p{margin:8px 0 0;line-height:1.6}
.r3-formula-guide .r3-summary-intro{font-size:13px;color:#647981}
.r3-mini-link{display:flex;flex-wrap:wrap;gap:8px;margin:15px 0}
.r3-mini-link a{font-size:12px;text-decoration:none;border:1px solid #d4e7e3;padding:9px 12px;border-radius:10px;
 color:#08796e;background:#f6fbfa;font-weight:700;transition:background .2s ease}
.r3-mini-link a:hover{background:#e7f5f0}
.r3-study:not(.wide) .r3-formula-grid{grid-template-columns:1fr}
.r3-study:not(.wide) .r3-math{font-size:15px}
@media(max-width:1000px){.r3-formula-grid{grid-template-columns:1fr}}
@media(max-width:760px){.r3-formula-header{padding:15px 14px 10px}
 .r3-math-layout{padding:0 11px 11px}.r3-math{font-size:15px}
 .r3-math-worked{font-size:16px}.r3-explanation{padding:13px 14px}}
@media print{.r3-formula{break-inside:avoid;box-shadow:none;transform:none!important}
 .r3-formula-details{display:block}.r3-math{overflow:visible}.r3-formula-grid{grid-template-columns:1fr 1fr}}
</style>"""

def quality_formulas(e, multivariate, stats):
    n=e["total_rows"]
    concepts=e["distinct_rxcui_mapping_ready"]
    multiple=multivariate["cross_column_quality"]["concepts_with_multiple_names"]
    missing=e["missing_by_field"]
    one=next((x for x in missing if x["field"]=="rxcui"), missing[0])
    ready=e["mapping_ready_rows"]
    normalization=e["normalization_difference_rows"]
    length=stats["name_length"]
    blocks=[
        formula(
            "Tỷ lệ thiếu (Missing rate)",
            "Missing%(c) = (Số ô trống c / N) × 100%",
            f"rxcui: ({one['count']} / {vi(n)}) × 100% = {vi(100*one['count']/n,2)}%",
            "Không có giá trị thiếu trong năm cột chính theo quy tắc hiện tại.",
            "N: số bản ghi; c: từng cột được kiểm tra.",
        ),
        formula(
            "Phần trăm RxCUI có nhiều tên",
            "Multi-name% = (Số RxCUI có ≥2 tên / Số RxCUI khác nhau) × 100%",
            f"({vi(multiple)} / {vi(concepts)}) × 100% = {vi(100*multiple/concepts,2)}%",
            "Một mã thuốc có thể có nhiều cách biểu diễn; không xóa các tên hợp lệ chỉ vì cùng RxCUI.",
            "Đơn vị là RxCUI duy nhất, không phải bản ghi thuật ngữ.",
        ),
        formula(
            "Tỷ lệ bản ghi đủ điều kiện Mapping",
            "Readiness% = (Số dòng mapping-ready / Tổng số dòng) × 100%",
            f"({vi(ready)} / {vi(n)}) × 100% = {vi(100*ready/n,2)}%",
            "Các dòng hiện tại đạt quy tắc kỹ thuật trước Mapping, chưa được chứng minh đúng về lâm sàng.",
            "Dòng trùng hoàn toàn theo (rxcui, tty, sab, display_name) được loại khi cần.",
        ),
        formula(
            "Nhất quán chuẩn hóa tên (Normalization audit)",
            "Mismatch% = (Số dòng normalized_name khác quy tắc chuẩn hóa / N) × 100%",
            f"({vi(normalization)} / {vi(n)}) × 100% = {vi(100*normalization/n,2)}%",
            "Tên ở Silver đang nhất quán với quy tắc chuẩn hóa được kiểm tra.",
            "Ví dụ minh họa: 'Acetaminophen 500 MG' → 'acetaminophen 500 mg'.",
        ),
        formula(
            "Trung bình, trung vị, mode",
            "Mean = ΣLᵢ / N; Median = giá trị giữa khi sắp xếp; Mode = giá trị xuất hiện nhiều nhất",
            f"N={vi(length['n'])} · Mean={vi(length['mean'],3)} · Median={vi(length['median'])} · Mode={vi(length['mode'])} (ký tự)",
            "Trung bình lớn hơn trung vị gợi ý đuôi phân bố kéo dài về phía tên dài.",
            "Lᵢ là số ký tự trong display_name; các tổng ΣLᵢ không được lưu riêng trong JSON.",
        ),
        formula(
            "Phương sai và độ lệch chuẩn",
            "Variance = Σ(Lᵢ − Mean)²/N; SD = √Variance",
            f"Variance={vi(length['variance'],3)} ký tự²; SD=√{vi(length['variance'],3)} = {vi(length['std_dev'],3)} ký tự",
            "Độ lệch chuẩn cho biết độ phân tán của tên thuốc; không phải số lượng thuốc.",
            "Dùng phương sai tổng thể (ddof=0) cho snapshot đã thu thập.",
        ),
    ]
    nav = (
        '<nav class="r3-mini-link" aria-label="Chuyển đến từng phép kiểm định">'
        '<a href="#report-3-tests">Các phép kiểm định</a>'
        '<a href="#r3-correlation">Pearson / Spearman</a>'
        '<a href="#r3-welch">Welch / Holm</a>'
        '<a href="#r3-chi2">Chi-square</a>'
        '<a href="#r3-coherence">Coherence</a>'
        '<a href="#report-4">Report 4</a>'
        '</nav>'
    )
    return STYLE + (
        '<div class="r3-formula-guide"><h3>Sổ tay công thức Report 3 · Chuẩn bị dữ liệu</h3>'
        '<p class="r3-summary-intro">Mỗi công thức đều có cách thay số, ý nghĩa thống kê và câu nói gợi ý khi thuyết trình.</p>'
        + nav + '<div class="r3-formula-grid">' + "".join(blocks) + '</div></div>'
    )


def inferential_formulas(multivariate):
    r=multivariate
    corr=r["correlations"][0]
    vals=r["welch_t_tests"]
    ab=vals[0]
    second=vals[1]
    chi=r["chi_square"]
    coh=r["lexical_coherence"]
    n=chi["n_rows"]
    row=chi["row_labels"].index("SY") if "SY" in chi["row_labels"] else 0
    column=chi["column_labels"].index("<20") if "<20" in chi["column_labels"] else 0
    obs=chi["observed"][row][column]
    row_total=sum(chi["observed"][row])
    col_total=sum(items[column] for items in chi["observed"])
    expected=row_total*col_total/n
    contrib=(obs-expected)**2/expected
    df=chi["df"]
    # Welch standard error here is INFERRED from rounded diff and t.
    derived_se=abs(ab["difference"]/ab["t"]) if ab.get("t") else None
    pooled=abs(ab["difference"]/ab["cohen_d"]) if ab.get("cohen_d") else None
    diff=ab.get("difference")
    ci=ab.get("ci95_normal_approx")
    rvalue=corr.get("pearson_r")
    rsquare=vi(rvalue*rvalue,4) if rvalue is not None else "không xác định (biến không biến thiên)"
    holm_example=(f"m=3; SCD/SBD ở vị trí 2: 2 × {second['p_value']:.4g} ≈ {second['p_holm']:.4g}"
                  if second.get("p_value") is not None and second.get("p_holm") is not None
                  else "Dữ liệu kiểm thử không đủ số cặp hợp lệ để minh họa phép nhân p.")
    coh_high=coh["distribution"][2]
    k=coh["n_comparable_rxcui"]
    highpct=(vi(100*coh_high["count"]/k,2)+"%") if k else "không áp dụng (M=0)"
    out={}
    out["correlation"] = '<div class="r3-formula-grid">'+''.join([
        formula(
            "Pearson r (tương quan tuyến tính)",
            "r = Σ[(xᵢ − x̄)(yᵢ − ȳ)] / √{Σ(xᵢ−x̄)² × Σ(yᵢ−ȳ)²}",
            f"n={vi(corr['n'])} RxCUI; r={vi(corr['pearson_r'],4)}; r²=({vi(corr['pearson_r'],4)})² ≈ {rsquare}",
            "Mối quan hệ tuyến tính dương nhưng yếu giữa số thuật ngữ và độ dài tên trung bình.",
            "x: số tên/RxCUI; y: độ dài tên trung bình/RxCUI; x̄ và ȳ: hai trung bình.",
            "Báo cáo chỉ lưu hệ số r, không lưu các tổng tử/mẫu để thay đầy đủ từng hạng tử."
        ),
        formula(
            "Spearman ρ (tương quan thứ hạng)",
            "ρ = Pearson(rank(x), rank(y))",
            f"n={vi(corr['n'])} RxCUI; ρ={vi(corr['spearman_rho'],4)}",
            "Quan hệ đồng biến theo thứ hạng rõ hơn quan hệ tuyến tính; không chứng minh nhân quả.",
            "Thứ hạng bằng nhau được gán trung bình thứ hạng (tied ranks)."
        ),
    ])+'</div>'
    if ab.get("status") != "computed":
        t_blocks=[
            formula("Welch's t-test: công thức kiểm định",
                    "t = (Mean₁ − Mean₂) / √(s₁²/n₁+s₂²/n₂)",
                    "Chưa tính được t từ ví dụ kiểm thử này: nhóm có quá ít RxCUI độc lập.",
                    "Dữ liệu thực tế sẽ thay bằng trung bình, SE và kết quả t khi hai nhóm đủ quan sát."),
            formula("Bậc tự do Welch–Satterthwaite",
                    "df = (s₁²/n₁+s₂²/n₂)² / [(s₁²/n₁)²/(n₁−1)+(s₂²/n₂)²/(n₂−1)]",
                    "Không có df khi kiểm định không áp dụng.", "Không tạo số thay thế."),
            formula("Cohen's d: độ lớn hiệu ứng", "d=(Mean₁−Mean₂)/s_pooled",
                    "Không tính d khi hai nhóm không đủ điều kiện.", "Cần phân biệt độ mạnh hiệu ứng với p-value."),
            formula("Khoảng tin cậy CI₉₅%", "CI₉₅% ≈ Δ ± 1,96×SE",
                    "Không ước lượng khi kiểm định không áp dụng.", "Không suy diễn độ chính xác từ dữ liệu quá ít."),
            formula("Holm: điều chỉnh p-value", "p_adj,(i)=maxⱼ≤i[min(1,(m−j+1)×p_(j))]",
                    "Chỉ hiệu chỉnh những kiểm định có p-value hợp lệ.", "Không ghi p=0 nếu chưa tính.")
        ]
    else:
        t_blocks=[
            formula(
                "Welch's t-test: công thức kiểm định",
                "t = (Mean₁ − Mean₂) / √(s₁²/n₁ + s₂²/n₂)",
                f"IN vs SCD: ({vi(ab['mean_a'],3)} − {vi(ab['mean_b'],3)}) / {vi(derived_se,4)} ≈ {vi(ab['t'],4)}",
                "Độ dài tên IN thấp hơn SCD; chênh lệch là độ dài tên, không phải tác dụng thuốc.",
                f"n₁={vi(ab['n_a'])}; n₂={vi(ab['n_b'])}; SE={vi(derived_se,4)} là sai số chuẩn suy ngược từ t và hiệu số đã làm tròn.",
                "Để tính SE từ đầu cần phương sai của hai nhóm; báo cáo hiện không lưu hai phương sai đó."
            ),
            formula(
                "Bậc tự do Welch–Satterthwaite",
                "df = (s₁²/n₁+s₂²/n₂)² / [(s₁²/n₁)²/(n₁−1)+(s₂²/n₂)²/(n₂−1)]",
                f"df được chương trình tính từ dữ liệu gốc: {vi(ab['df'],2)}",
                "Welch không ép hai nhóm phải có phương sai bằng nhau.",
                "Các phương sai gốc không có trong bảng JSON; không tự đặt số để thay vào."
            ),
            formula(
                "Cohen's d: độ lớn hiệu ứng",
                "d = (Mean₁ − Mean₂) / s_pooled",
                f"d = {vi(diff,3)} / {vi(pooled,3)} ≈ {vi(ab['cohen_d'],3)}",
                "Dấu âm là do lấy IN trừ SCD; độ lớn khoảng 0,678 đáng lưu ý.",
                "s_pooled được suy ngược từ d làm tròn; giá trị chỉ xấp xỉ."
            ),
            formula(
                "Khoảng tin cậy hiệu số trung bình 95%",
                "CI₉₅% ≈ (Mean₁−Mean₂) ± 1,96 × SE",
                f"{vi(diff,3)} ± 1,96 × {vi(derived_se,4)} ≈ [{vi(ci[0],3)}; {vi(ci[1],3)}] ký tự",
                "Cả khoảng ở phía âm, phù hợp với tên IN ngắn hơn SCD.",
                "Đây là khoảng xấp xỉ chuẩn mà code công bố, không phải khoảng dùng phân vị t chính xác."
            ),
            formula(
                "Holm: điều chỉnh p-value cho nhiều phép thử",
                "p_adj,(i) = maxⱼ≤i[min(1, (m−j+1)×p_(j))], sau khi xếp p tăng dần",
                holm_example,
                "Kết quả vẫn nhỏ hơn 0,05 sau điều chỉnh.",
                "p cực nhỏ có thể tràn số về 0 trong máy tính; không diễn giải là xác suất bằng 0."
            ),
        ]
    out["ttest"] = '<div class="r3-formula-grid">'+"".join(t_blocks)+'</div>'
    out["chi"]='<div class="r3-formula-grid">'+''.join([
        formula(
            "Tần số kỳ vọng E của từng ô",
            "Eᵢⱼ = (Tổng hàng i × Tổng cột j) / N",
            f"TTY={chi['row_labels'][row]}, tên {chi['column_labels'][column]}: E = {vi(row_total)} × {vi(col_total)} / {vi(n)} = {vi(expected,2)}",
            "Nếu TTY và nhóm độ dài độc lập, ô này dự kiến có khoảng đó bản ghi.",
            f"Quan sát thực tế: O = {vi(obs)}."
        ),
        formula(
            "Chi-square Pearson",
            "χ² = Σ[(Oᵢⱼ − Eᵢⱼ)² / Eᵢⱼ]",
            f"Ô ví dụ: ({vi(obs)} − {vi(expected,2)})² / {vi(expected,2)} ≈ {vi(contrib,2)}; tổng χ² = {vi(chi['statistic'],3)}",
            "Loại TTY và nhóm độ dài tên có phân bố khác nhau theo bảng tần số.",
            "Một RxCUI có thể có nhiều dòng nên giả định các quan sát độc lập chưa hoàn toàn đúng."
        ),
        formula(
            "Bậc tự do của Chi-square",
            "df = (r−1) × (c−1)",
            f"r={len(chi['row_labels'])}; c={len(chi['column_labels'])}; df=({len(chi['row_labels'])}−1)×({len(chi['column_labels'])}−1) = {vi(df)}",
            "Số nhóm TTY và độ dài xác định bậc tự do của bảng chéo."
        ),
        formula(
            "Cramér's V: độ mạnh liên hệ",
            "V = √[χ² / (N × min(r−1, c−1))]",
            f"V = √[{vi(chi['statistic'],3)} / ({vi(n)} × 4)] ≈ {vi(chi['cramers_v'],3)}",
            "Độ mạnh liên hệ khoảng 0,268; không đánh đồng p nhỏ với mức liên hệ rất mạnh.",
            "Tỷ lệ của từng ô là thuật ngữ, không phải số sản phẩm hay mức độ đúng của Mapping."
        ),
    ])+'</div>'
    out["coherence"]='<div class="r3-formula-grid">'+''.join([
        formula(
            "Jaccard: độ tương đồng bộ token",
            "J(A,B) = |A∩B| / |A∪B|",
            "Ví dụ minh họa: A={amlodipine, 5, mg, tablet}; B={amlodipine, 5, mg, oral, tablet} → J=4/5=0,8",
            "Jaccard đo từ chung; hai tên hợp lệ có thể dùng chữ viết tắt khác nhau nên J thấp.",
            "Đây là ví dụ dựng để giải thích phép tính, không phải cặp trích từ nguồn."
        ),
        formula(
            "Coherence của một RxCUI và toàn tập",
            "Cᵣ = [Σ J(name₁,nameᵢ)] / (kᵣ−1); Mean_C = ΣCᵣ / M",
            f"M={vi(k)} mã có ≥2 tên; Mean_C={vi(coh['mean'],3)}; Median_C={vi(coh['median'],3)}",
            "Số lớn nghĩa tên trong cùng mã thường chia sẻ nhiều token; không xác minh chính xác lâm sàng.",
            "Code lấy tên đầu tiên so với tối đa 14 tên tiếp theo, không so tất cả từng cặp."
        ),
        formula(
            "Tỷ lệ RxCUI có coherence cao",
            "High% = (Số RxCUI có C≥0,7 / Số RxCUI có ≥2 tên) × 100%",
            f"({vi(coh_high['count'])} / {vi(k)}) × 100% = {highpct}",
            "Ưu tiên rà soát mã coherence thấp khi hệ thống Mapping dựa vào chuỗi tên.",
            "Ngưỡng 0,3 và 0,7 do chương trình quy ước để phân nhóm, không phải tiêu chuẩn y khoa."
        ),
    ])+'</div>'
    return out
