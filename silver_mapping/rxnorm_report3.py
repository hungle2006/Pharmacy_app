"""RxNorm Report 3: cross-column profiling, lexical coherence and exploratory tests.

Grain: a deduplicated terminology row for categorical profiles; a unique RxCUI
for concept-level correlations and independent-group Welch tests.
No clinical/semantic equivalence assertions or causal/predictive inference.
Uses only Python standard library for reproducible GitHub Actions runs.
"""
from __future__ import annotations
import csv
import html
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

def nfmt(x):
    if x is None:return "—"
    if isinstance(x,int):return format(x,",")
    if abs(x)<.0001 and x!=0:return f"{x:.3e}"
    return f"{x:,.4f}"

def regularized_beta(a,b,x):
    """Numerical Recipes continued fraction; incomplete beta I_x(a,b)."""
    if x<=0:return 0.
    if x>=1:return 1.
    def cf(a,b,x):
        fpm=1e-300
        qab=a+b;qap=a+1;qam=a-1
        c=1.;d=1-qab*x/qap
        if abs(d)<fpm:d=fpm
        d=1/d;h=d
        for m in range(1,300):
            m2=2*m
            aa=m*(b-m)*x/((qam+m2)*(a+m2))
            d=1+aa*d
            if abs(d)<fpm:d=fpm
            c=1+aa/c
            if abs(c)<fpm:c=fpm
            d=1/d;h*=d*c
            aa=-(a+m)*(qab+m)*x/((a+m2)*(qap+m2))
            d=1+aa*d
            if abs(d)<fpm:d=fpm
            c=1+aa/c
            if abs(c)<fpm:c=fpm
            d=1/d
            delta=d*c
            h*=delta
            if abs(delta-1)<1e-12:break
        return h
    factor=math.exp(math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b)+a*math.log(x)+b*math.log1p(-x))
    return min(1.,max(0., factor*cf(a,b,x)/a if x<(a+1)/(a+b+2)
            else 1-factor*cf(b,a,1-x)/b))

def student_t_two_sided(t, df):
    return regularized_beta(df/2,0.5,df/(df+t*t))

def chi_square_survival(stat,df):
    """Regularized upper incomplete Gamma: Q(df/2, chi2/2)."""
    if stat<=0:return 1.
    a=df/2;x=stat/2
    if x<a+1:
        term=1/a;total=term
        for n in range(1,1000):
            term*=x/(a+n);total+=term
            if abs(term)<abs(total)*1e-13:break
        p=total*math.exp(-x+a*math.log(x)-math.lgamma(a))
        return min(1.,max(0.,1-p))
    b=x+1-a;c=1e300;d=1/b;h=d
    for i in range(1,1000):
        an=-i*(i-a)
        b+=2
        d=an*d+b
        if abs(d)<1e-300:d=1e-300
        c=b+an/c
        if abs(c)<1e-300:c=1e-300
        d=1/d
        delta=d*c
        h*=delta
        if abs(delta-1)<1e-13:break
    return min(1.,max(0.,math.exp(a*math.log(x)-x-math.lgamma(a))*h))

def pearson(x,y):
    if len(x)<3:return None
    mx=statistics.fmean(x);my=statistics.fmean(y)
    xx=yy=xy=0.
    for a,b in zip(x,y):
        da=a-mx;db=b-my
        xx+=da*da; yy+=db*db;xy+=da*db
    return xy/math.sqrt(xx*yy) if xx>0 and yy>0 else None

def ranks(values):
    indexes=sorted(range(len(values)),key=lambda k:values[k])
    out=[0.]*len(values)
    i=0
    while i<len(values):
        j=i+1
        while j<len(values) and values[indexes[j]]==values[indexes[i]]:j+=1
        midpoint=(i+1+j)/2
        for k in range(i,j):out[indexes[k]]=midpoint
        i=j
    return out

def holm(tests):
    eligible=sorted((t for t in tests if t.get("p_value") is not None),key=lambda d:d["p_value"])
    m=len(eligible);max_seen=0.
    for k,t in enumerate(eligible):
        max_seen=max(max_seen,min(1.,(m-k)*t["p_value"]))
        t["p_holm"]=max_seen

def welch(x,y,label):
    n1=len(x);n2=len(y)
    result={"comparison":label,"unit":"one independent RxCUI per group","n_a":n1,"n_b":n2,
            "method":"Welch unequal-variance t-test","p_value":None,"status":"not_applicable"}
    if min(n1,n2)<20:
        result["reason"]="Fewer than 20 independent RxCUI in a group";return result
    avg1=statistics.fmean(x);avg2=statistics.fmean(y)
    v1=statistics.variance(x);v2=statistics.variance(y)
    s1=v1/n1;s2=v2/n2
    if s1+s2==0:
        result["reason"]="Both groups have no variation";return result
    diff=avg1-avg2;se=math.sqrt(s1+s2)
    df=(s1+s2)**2/(s1*s1/(n1-1)+s2*s2/(n2-1)) if s1*s1/(n1-1)+s2*s2/(n2-1)>0 else None
    if df is None or df<=0:return result
    pooled=math.sqrt(((n1-1)*v1+(n2-1)*v2)/(n1+n2-2))
    result.update({"status":"computed","mean_a":round(avg1,3),"mean_b":round(avg2,3),
                   "difference":round(diff,3),"t":round(diff/se,4),"df":round(df,2),
                   "p_value":student_t_two_sided(diff/se,df),
                   "cohen_d":round(diff/pooled,3) if pooled>0 else None,
                   "ci95_normal_approx":[round(diff-1.96*se,3),round(diff+1.96*se,3)]})
    return result

def lex_tokens(value):
    return set(value.casefold().split())

def category_length(n):
    if n<20:return "<20"
    if n<40:return "20–39"
    if n<60:return "40–59"
    if n<100:return "60–99"
    return "≥100"

def profile(mapping_ready_csv, source_csv=None):
    """Tests on quality-gated terminology, missing-value audits on source CSV."""
    per_rxcui=defaultdict(lambda:{"terms":0,"length_sum":0,"max_length":0,"tty_set":set(),
                                  "tty_lengths":defaultdict(list),"tokens":[]})
    tty_tot=Counter();xy=Counter();band_tot=Counter()
    for path in (mapping_ready_csv,):
        with Path(path).open(newline="",encoding="utf-8-sig") as inp:
            reader=csv.DictReader(inp)
            for row in reader:
                id_=row["rxcui"].strip()
                tty=row["tty"].strip().upper()
                name=row["display_name"]
                n=len(name)
                group=category_length(n)
                rowkey=(tty,group)
                xy[rowkey]+=1
                tty_tot[tty]+=1
                band_tot[group]+=1
                p=per_rxcui[id_]
                p["terms"]+=1;p["length_sum"]+=n;p["max_length"]=max(p["max_length"],n)
                p["tty_set"].add(tty);p["tty_lengths"][tty].append(n)
                if len(p["tokens"])<15:p["tokens"].append(lex_tokens(row["normalized_name"] or name))
    if not per_rxcui:raise ValueError("Cannot compute Report 3 without mapping-ready RxNorm")
    # Concept-level (not repeated terminology rows) prevents pseudoreplication.
    x=[];y=[];maxlens=[];type_counts=[]
    tty_averages=defaultdict(dict)
    coherence=[];coherence_cases=[]
    single_count=0
    for rxcui,item in per_rxcui.items():
        terms=item["terms"];x.append(terms)
        y.append(item["length_sum"]/terms)
        maxlens.append(item["max_length"])
        type_counts.append(len(item["tty_set"]))
        for tty,values in item["tty_lengths"].items():
            tty_averages[tty][rxcui]=statistics.fmean(values)
        tokens=item["tokens"]
        if len(tokens)<2:
            single_count+=1
            continue
        # Text overlap (not clinical coherence) between each term name and first name.
        base=tokens[0]
        similarities=[]
        for other in tokens[1:]:
            union=base|other
            similarities.append(len(base&other)/len(union) if union else 1.)
        sim=statistics.fmean(similarities)
        coherence.append(sim)
        if len(coherence_cases)<8 and sim<0.3:
            coherence_cases.append({"rxcui":rxcui,"jaccard":round(sim,3),
                                    "sampled_names":len(tokens),
                                    "n_terms_in_concept":terms})
    corrs=[]
    for (name1,name2,a,b) in [
        ("terms_per_rxcui","avg_name_length",x,y),
        ("terms_per_rxcui","max_name_length",x,maxlens),
        ("distinct_tty_per_rxcui","terms_per_rxcui",type_counts,x),
        ("distinct_tty_per_rxcui","avg_name_length",type_counts,y)]:
        r=pearson(a,b)
        s=pearson(ranks(a),ranks(b)) if r is not None else None
        corrs.append({"x":name1,"y":name2,"n":len(a),
                      "pearson_r":round(r,4) if r is not None else None,
                      "spearman_rho":round(s,4) if s is not None else None,
                      "unit":"unique RxCUI"})
    pairs=[("IN","SCD"),("SCD","SBD"),("SY","PSN")]
    tt=[]
    for a,b in pairs:
        a_ids=tty_averages.get(a,{});b_ids=tty_averages.get(b,{})
        # Exclusively one TTY in each compared pair, avoiding overlapping concepts.
        a_only=set(a_ids)-set(b_ids);b_only=set(b_ids)-set(a_ids)
        vals_a=[a_ids[k] for k in a_only]
        vals_b=[b_ids[k] for k in b_only]
        test=welch(vals_a,vals_b,f"{a} vs {b}")
        test["group_a"]=a;test["group_b"]=b
        test["overlapping_rxcui_excluded"]=len(set(a_ids)&set(b_ids))
        tt.append(test)
    holm(tt)
    selected=[k for k,_ in tty_tot.most_common(8)]
    selected.append("Khác")
    length_labels=["<20","20–39","40–59","60–99","≥100"]
    mat=defaultdict(Counter)
    for (tty,group),n in xy.items():
        bucket=tty if tty in selected else "Khác"
        mat[bucket][group]+=n
    observed=[[mat[k][b] for b in length_labels] for k in selected]
    row_sums=[sum(row) for row in observed]
    col_sums=[sum(row[i] for row in observed) for i in range(len(length_labels))]
    n=sum(row_sums)
    df=(len(selected)-1)*(len(length_labels)-1)
    chi2=sum((actual-row_sums[i]*col_sums[j]/n)**2/(row_sums[i]*col_sums[j]/n)
             for i,row in enumerate(observed) for j,actual in enumerate(row)
             if row_sums[i]*col_sums[j]>0)
    min_expected=min(row_sums[i]*col_sums[j]/n for i in range(len(selected))
                     for j in range(len(length_labels)) if row_sums[i]*col_sums[j]>0)
    cramer=math.sqrt(chi2/(n*min(len(selected)-1,len(length_labels)-1)))
    chi={"columns":["tty","derived_name_length_bin"],"method":"Pearson chi-square",
         "n_rows":n,"statistic":round(chi2,3),"df":df,"p_value":chi_square_survival(chi2,df),
         "cramers_v":round(cramer,4),"min_expected_cell":round(min_expected,3),
         "valid_expected_counts":min_expected>=5,
         "unit":"terminology row; RxCUI repeated (independence assumption not strictly met)",
         "row_labels":selected,"column_labels":length_labels,
         "observed":observed}
    source_counts=Counter();qc_by_tty=Counter();sab=Counter();norm_missing=Counter()
    if source_csv:
        with Path(source_csv).open(encoding="utf-8-sig",newline="") as f:
            for row in csv.DictReader(f):
                source_counts["total"]+=1
                for col in ("normalized_name","rxcui","display_name","tty","sab"):
                    if not (row.get(col) or "").strip():
                        norm_missing[col]+=1
                qc_by_tty[(row.get("tty") or "").strip().upper(),(row.get("silver_qc_status") or "").upper()]+=1
                sab[(row.get("sab") or "").upper()]+=1
    coherence_counts=Counter("low (<0.3)" if s<.3 else "medium (0.3–0.7)" if s<.7 else "high (≥0.7)" for s in coherence)
    skipped=[]
    if len(sab)<=1:skipped.append({"test":"TTY × SAB chi-square","reason":"SAB has just one category in source; association undefined"})
    if len({k[1] for k in qc_by_tty})<=1:skipped.append({"test":"TTY × Silver QC chi-square","reason":"All records have same QC label; association undefined"})
    skipped.append({"test":"Cronbach alpha / reliability","reason":"RxNorm columns are terminology identifiers/text, not multiple items measuring one latent construct"})
    skipped.append({"test":"Normality test / one-sample t-test of RxCUI","reason":"RxCUI is an identifier, not a quantitative outcome"})
    return {
        "scope":"Exploratory cross-column RxNorm terminology analysis",
        "source_rows":source_counts["total"] or n,
        "analyzed_rows":n,"concepts":len(per_rxcui),
        "cross_column_quality":{"source_missing":dict(norm_missing),
           "tty_qc_unique_labels":len({k[1] for k in qc_by_tty}),
           "sab_unique_values":len(sab),"tty_unique_values":len(tty_tot),
           "concepts_with_multiple_names":len(coherence),"concepts_single_term":single_count},
        "correlations":corrs,
        "welch_t_tests":tt,
        "chi_square":chi,
        "lexical_coherence":{"metric":"average Jaccard token overlap versus first name within each RxCUI (up to 15 terms), not clinical equivalence",
           "n_comparable_rxcui":len(coherence),
           "mean":round(statistics.fmean(coherence),4) if coherence else None,
           "median":round(statistics.median(coherence),4) if coherence else None,
           "distribution":[{"label":k,"count":coherence_counts[k]} for k in ("low (<0.3)","medium (0.3–0.7)","high (≥0.7)")],
           "review_examples":coherence_cases},
        "not_applicable":skipped,
        "interpretation_notes":[
            "All results are descriptive or exploratory for an observed source snapshot, not experiments or cause-effect evidence.",
            "Welch compares independent RxCUI after excluding concepts shared across the two TTY labels; p-values Holm-adjusted across three planned contrasts.",
            "Chi-square involves multiple names for the same RxCUI and violates strict observation independence. Treat p-values as diagnostic only; prioritize Cramer's V.",
            "Extremely large sample sizes can yield very small p-values for negligible effect sizes.",
            "Distinct TTY count and term count are arithmetically related: a high correlation is partly mechanical, not a novel clinical finding.",
            "Lexical Jaccard measures text overlap, not synonym truth, therapeutic equivalence or clinical correctness.",
            "No distribution normality or independence is guaranteed. No time-series tests on a single snapshot."
        ]
    }

def render_report3(result):
    def h(s):return html.escape(str(s),quote=True)
    def num(x):return nfmt(x)
    def pvalue(x):
        if x is None:return "—"
        if x == 0:return "<1e-300 (underflow)"
        return f"{x:.3g}"
    def table(header,rows):
        return '<div class="r3-table-scroll"><table class="r3-table"><thead><tr>'+''.join('<th>'+h(c)+'</th>' for c in header)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+h(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    r=result
    corr=table(["Cột X","Cột Y","N (RxCUI)","Pearson r","Spearman ρ"],
              [[q["x"],q["y"],num(q["n"]),num(q["pearson_r"]),num(q["spearman_rho"])] for q in r["correlations"]])
    trows=[]
    for q in r["welch_t_tests"]:
        trows.append([q["comparison"],num(q["n_a"]),num(q["n_b"]),
                     num(q.get("t")),num(q.get("df")),pvalue(q.get("p_value")),pvalue(q.get("p_holm")),
                     num(q.get("cohen_d")),q["status"]])
    ttest=table(["So sánh","N A","N B","t","df","p","p Holm","Cohen d","Trạng thái"],trows)
    c=r["chi_square"]
    heat='<div class="r3-table-scroll"><table class="r3-table"><thead><tr><th>TTY</th>'+''.join('<th>'+h(k)+'</th>' for k in c["column_labels"])+'</tr></thead><tbody>'
    peak=max((max(v) for v in c["observed"]),default=1)
    for label,line in zip(c["row_labels"],c["observed"]):
        heat+='<tr><th>'+h(label)+'</th>'+''.join('<td style="background:rgba(19,140,129,'+str(round(.06+.38*v/peak,3))+')">'+num(v)+'</td>' for v in line)+'</tr>'
    heat+='</tbody></table></div>'
    coher=r["lexical_coherence"]
    coh=table(["Mức nhất quán từ ngữ","Số RxCUI"],[[p["label"],num(p["count"])] for p in coher["distribution"]])
    excluded=table(["Phép thử không thực hiện","Lý do"],[[q["test"],q["reason"]] for q in r["not_applicable"]])
    css="""<style>.r3-multivariate{margin-top:22px}.r3-head{margin:8px 0 18px}.r3-head h2{font-size:26px;margin:0 0 8px}.r3-head p{max-width:910px}.r3-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.r3-study{background:#fff;border:1px solid #dce9ea;border-radius:17px;padding:20px;min-width:0}.r3-study h3{font-size:18px;margin:0 0 8px;color:#21495a}.r3-study p{font-size:13px}.r3-study.wide{grid-column:1/-1}.r3-pill{display:inline-block;border-radius:999px;padding:5px 10px;font-weight:750;color:#08796e;background:#e5f5f0;font-size:11px}.r3-table-scroll{max-width:100%;overflow:auto}.r3-table{width:100%;border-collapse:collapse;font-size:12px}.r3-table th,.r3-table td{padding:9px 8px;border-bottom:1px solid #e7eeee;white-space:nowrap;text-align:left}.r3-table th{font-size:11px;color:#506b78}.r3-meta{color:#536d78;font-size:12px}.r3-callout{background:#f0f7f6;border-left:3px solid #0e8b80;border-radius:9px;padding:14px 16px;margin-top:16px;font-size:13px;color:#335866}.r3-facts{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}.r3-facts span{padding:12px 16px;border-radius:12px;background:#eaf6f3;font-size:12px}.r3-facts strong{display:block;font-size:20px;color:#134f4e}@media(max-width:830px){.r3-grid{grid-template-columns:1fr}.r3-study.wide{grid-column:auto}}</style>"""
    summary='<div class="r3-facts"><span>Thuật ngữ phân tích<strong>'+num(r["analyzed_rows"])+'</strong></span><span>RxCUI<strong>'+num(r["concepts"])+'</strong></span><span>TTY khác nhau<strong>'+num(r["cross_column_quality"]["tty_unique_values"])+'</strong></span><span>RxCUI có nhiều tên<strong>'+num(coher["n_comparable_rxcui"])+'</strong></span></div>'
    return (css+'<section class="r3-multivariate" id="report-3-tests"><div class="r3-head"><span class="r3-pill">REPORT 3 · MULTIVARIATE EDA</span><h2>Kiểm định thống kê giữa các cột dữ liệu</h2><p>Correlation, Welch t-test, χ² / Cramér’s V và consistency giữa các tên cùng RxCUI. Chọn phép kiểm định theo thang đo; RxCUI là mã định danh, không phải số liên tục.</p></div>'+summary+
        '<div class="r3-grid"><article class="r3-study wide"><h3>01 · Correlation matrix · Tương quan trên mỗi RxCUI</h3><p>Pearson r và Spearman ρ giữa số tên, độ dài tên và số nhóm TTY. Mỗi RxCUI chỉ được tính một lần.</p>'+corr+'</article>'+
        '<article class="r3-study wide"><h3>02 · Welch’s independent t-tests</h3><p>So sánh trung bình độ dài tên giữa các nhóm TTY. Loại các RxCUI thuộc cả hai nhóm, có hiệu chỉnh Holm cho nhiều phép thử; kèm Cohen d để đánh giá cường độ khác biệt.</p>'+ttest+'</article>'+
        '<article class="r3-study"><h3>03 · χ² · Categorical association</h3><p>TTY × nhóm độ dài tên. χ²='+num(c["statistic"])+', df='+num(c["df"])+', Cramér V='+num(c["cramers_v"])+'. Đơn vị kiểm định là dòng thuật ngữ, nên giả định độc lập chưa hoàn toàn đúng.</p>'+heat+'</article>'+
        '<article class="r3-study"><h3>04 · Coherence · Nhất quán nội bộ</h3><p>Jaccard token overlap của các tên chung một RxCUI (tối đa 15 tên mỗi mã). Trung bình='+num(coher["mean"])+', trung vị='+num(coher["median"])+'. Đây là sự nhất quán <strong>về mặt từ vựng</strong>, không đo tính đúng đắn lâm sàng.</p>'+coh+'</article>'+
        '<article class="r3-study wide"><h3>05 · Những kiểm định không nên thực hiện</h3>'+excluded+'</article></div>'+
        '<div class="r3-callout"><strong>Giới hạn diễn giải:</strong> Đây là dữ liệu quan sát từ một snapshot. p-value rất nhỏ với N lớn không đồng nghĩa tác động thực tế lớn; cần xem độ lớn hiệu ứng và giả định độc lập. Không suy ra tương đương điều trị hoặc nhân quả từ các phép kiểm định này.</div></section>')
