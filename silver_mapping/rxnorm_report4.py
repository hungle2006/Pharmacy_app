"""Lecture-aligned descriptive statistics and chart rendering for RxNorm Trực quan hóa thống kê.

Course 6.1-6.4: categorical bar/pie, numeric histogram, box plot, scatter.
No manufactured time series, fitted normal curve, or clinical associations.
"""
from __future__ import annotations

import csv
import html
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

def safe(value):
    return html.escape(str(value), quote=True)

def fmt(value, decimals=0):
    return chart_number(value, decimals)

def quantile(sorted_values, p):
    """Linear interpolation, 0-based; n=0 returns None."""
    if not sorted_values:
        return None
    at = (len(sorted_values) - 1) * p
    low = int(at)
    high = math.ceil(at)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (at - low)

def summary(values):
    nums = sorted(values)
    if not nums:
        return {"n":0}
    q1 = quantile(nums, .25)
    q3 = quantile(nums, .75)
    fence_low = q1 - 1.5 * (q3 - q1)
    fence_high = q3 + 1.5 * (q3 - q1)
    low = next(v for v in nums if v >= fence_low)
    high = next(v for v in reversed(nums) if v <= fence_high)
    modes=Counter(nums).most_common()
    freq=modes[0][1]
    return {
        "n":len(nums),"min":nums[0],"max":nums[-1],
        "mean":round(statistics.fmean(nums),3),
        "median":round(quantile(nums,.5),3),
        "mode":min(v for v,n in modes if n==freq),
        "variance":round(statistics.pvariance(nums),3),
        "std_dev":round(statistics.pstdev(nums),3),
        "q1":round(q1,3),"q3":round(q3,3),
        "iqr":round(q3-q1,3),
        "whisker_low":low,"whisker_high":high,
        "outliers":sum(x<fence_low or x>fence_high for x in nums),
    }

def correlation(xs,ys):
    if len(xs)<2:
        return None
    mx=statistics.fmean(xs); my=statistics.fmean(ys)
    a=b=c=0.
    for x,y in zip(xs,ys):
        xx=x-mx;yy=y-my
        a+=xx*yy;b+=xx*xx;c+=yy*yy
    return round(a/math.sqrt(b*c),4) if b>0 and c>0 else None

def compute_report4(mapping_ready_csv):
    """Every statistic computed on distinct usable terminology rows in mapping-ready CSV."""
    lengths=[];by_tty=defaultdict(list);ttys=Counter()
    per_concept=defaultdict(lambda:[0,0])
    with Path(mapping_ready_csv).open(encoding="utf-8-sig",newline="") as f:
        rows=csv.DictReader(f)
        for row in rows:
            length=len(row["display_name"])
            tty=row["tty"].strip().upper()
            rx=row["rxcui"].strip()
            lengths.append(length)
            by_tty[tty].append(length)
            ttys[tty]+=1
            per_concept[rx][0]+=1
            per_concept[rx][1]+=length
    if not lengths:
        raise ValueError("Trực quan hóa thống kê requires at least one RxNorm term")
    bins=Counter()
    for length in lengths:
        label=f"{length//10*10}-{length//10*10+9}" if length<100 else "100+"
        bins[label]+=1
    hist=[{"bin":f"{i}-{i+9}","count":bins[f"{i}-{i+9}"]} for i in range(0,100,10)]
    hist.append({"bin":"100+","count":bins["100+"]})
    termfreq=Counter(v[0] for v in per_concept.values())
    interval_counts={
        "1":termfreq[1],"2":termfreq[2],"3":termfreq[3],
        "4-5":termfreq[4]+termfreq[5],
        "6-10":sum(count for n,count in termfreq.items() if 6<=n<=10),
        "11-20":sum(count for n,count in termfreq.items() if 11<=n<=20),
        "21+":sum(count for n,count in termfreq.items() if n>=21)
    }
    top=[k for k,_ in ttys.most_common(6)]
    category_boxes=[{"tty":k,**summary(by_tty[k])} for k in top]
    xs=[v[0] for v in per_concept.values()]
    ys=[v[1]/v[0] for v in per_concept.values()]
    # Small deterministic stratified subset purely for displaying individual dots.
    buckets=defaultdict(list)
    for rx,(count,total_length) in sorted(per_concept.items(),key=lambda x:int(x[0])):
        group="1" if count==1 else "2" if count==2 else "3-5" if count<=5 else "6-10" if count<=10 else "11+"
        buckets[group].append({"rxcui":rx,"terms":count,"avg_name_length":round(total_length/count,2)})
    scatter=[]
    for group in ("1","2","3-5","6-10","11+"):
        items=buckets.get(group,[])
        if not items:
            continue
        step=max(1,math.ceil(len(items)/85))
        scatter.extend(items[::step][:85])
    overall=summary(lengths)
    concept=summary(xs)
    pie=ttys.most_common(6)
    other=sum(ttys.values())-sum(k for _,k in pie)
    composition=[{"label":k,"count":n,"pct":round(n/len(lengths)*100,2)} for k,n in pie]
    if other:
        composition.append({"label":"Khác","count":other,"pct":round(other/len(lengths)*100,2)})
    return {
        "grain":"RxNorm terminology row, not a clinical product or longitudinal record",
        "n_terms":len(lengths),
        "n_rxcui":len(per_concept),
        "name_length_unit":"Unicode characters in display_name",
        "population_statistics":"population variance and SD (ddof=0) of this available RxNorm snapshot",
        "name_length":overall,
        "terms_per_rxcui":concept,
        "histogram_name_length":hist,
        "histogram_terms_per_rxcui":[{"bin":k,"count":v} for k,v in interval_counts.items()],
        "tty_distribution":[{"label":k,"count":n} for k,n in ttys.most_common()],
        "tty_composition":composition,
        "boxplot_by_tty":category_boxes,
        "scatter_illustrative":scatter,
        "scatter_sample_size":len(scatter),
        "pearson_all_rxcui":correlation(xs,ys),
        "scope_notice":"Không có chuỗi thời gian nhiều kỳ trong bản RxNorm này; không vẽ biểu đồ xu hướng hoặc kiểm định phân phối chuẩn khi thiếu cơ sở."
    }

def chart_number(value, decimals=0):
    return f"{value:,.{decimals}f}".replace(",", "_k_").replace(".", ",").replace("_k_", ".")


def chart_tip(label, value):
    return f' tabindex="0" data-tip="{safe(label)}" data-value="{safe(value)}"'


def svg_bar(rows, title, xfield, yfield, labels=None):
    rows=list(rows)
    if not rows:return ""
    left=83;right=735;bottom=255;top=30
    peak=max(int(row[yfield]) for row in rows) or 1;step=(right-left)/len(rows)
    unit="RxCUI" if title=="Term frequency" else "thuật ngữ"
    unit_label="Số RxCUI" if unit=="RxCUI" else "Số dòng thuật ngữ"
    scope="Số tên / RxCUI" if unit=="RxCUI" else "Ký tự / tên" if title=="Histogram length" else "Loại thuật ngữ TTY"
    parts=[f'<div class="ui-chart-caption"><span>{unit_label}</span><span>{scope}</span></div><svg class="r4-svg" viewBox="0 0 760 310" role="img" aria-label="{safe(title)}">']
    for k in range(5):
        val=peak*k/4;y=bottom-(bottom-top)*k/4
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" class="gridline"/><text x="{left-12}" y="{y+4:.1f}" text-anchor="end" class="ticks">{chart_number(round(val))}</text>')
    for ix,row in enumerate(rows):
        val=int(row[yfield]);height=(bottom-top)*val/peak;gap=.025 if title=="Histogram length" else .12
        x=left+ix*step+step*gap;width=step*(1-2*gap);y=bottom-height
        tip=chart_tip(row[xfield],f'{chart_number(val)} {unit}')
        label_class='ticks bin-label' if title=='Histogram length' else 'ticks'
        parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" rx="2" class="column"{tip}><title>{safe(row[xfield])}: {chart_number(val)} {unit}</title></rect><text x="{x+width/2:.2f}" y="{bottom+25}" text-anchor="middle" class="{label_class}">{safe(row[xfield])}</text>')
    return ''.join(parts)+'</svg>'


def svg_boxplots(groups):
    if not groups:return ""
    height=62+len(groups)*57;left=94;right=720;peak=max(10,max(g["whisker_high"] for g in groups));position=lambda value:left+(right-left)*value/peak
    parts=[f'<div class="ui-chart-caption"><span>Độ dài tên · ký tự</span><span>Q1 / Trung vị / Q3 · Râu 1,5 × IQR</span></div><svg class="r4-svg" viewBox="0 0 760 {height}" role="img" aria-label="Box plots: độ dài tên theo nhóm TTY">']
    for tick in range(5):
        x=left+(right-left)*tick/4
        parts.append(f'<line x1="{x:.1f}" y1="20" x2="{x:.1f}" y2="{height-32}" class="gridline"/><text x="{x:.1f}" y="{height-10}" text-anchor="middle" class="ticks">{chart_number(peak*tick/4,0)}</text>')
    for i,g in enumerate(groups):
        y=44+i*57;a=position(g["whisker_low"]);b=position(g["whisker_high"]);q1=position(g["q1"]);q3=position(g["q3"]);median=position(g["median"])
        parts.append(f'<text x="10" y="{y+4}" class="box-label">{safe(g["tty"])}</text><line x1="{a:.1f}" y1="{y}" x2="{b:.1f}" y2="{y}" class="whisker"/>')
        for x in (a,b):parts.append(f'<line x1="{x:.1f}" y1="{y-9}" x2="{x:.1f}" y2="{y+9}" class="whisker"/>')
        info=f'Q1 {chart_number(g["q1"],1)} · Trung vị {chart_number(g["median"],1)} · Q3 {chart_number(g["q3"],1)} ký tự · {chart_number(g["outliers"])} ngoại lai'
        parts.append(f'<rect x="{q1:.1f}" y="{y-15}" width="{max(1,q3-q1):.1f}" height="30" rx="3" class="box-fill"{chart_tip(g["tty"],info)}><title>{safe(info)}</title></rect><line x1="{median:.1f}" y1="{y-15}" x2="{median:.1f}" y2="{y+15}" class="median"/>')
    return ''.join(parts)+'</svg>'


def svg_donut(items):
    if not items:return ""
    total=sum(item['count'] for item in items)
    if not total:return ""
    palette=['var(--chart-primary)','var(--chart-secondary)','var(--chart-gold)','var(--chart-olive)','var(--chart-rose)','var(--chart-slate)'];tty={"SY":0,"PSN":1,"SCD":2,"SCDC":3,"TMSY":4,"SBD":5}
    color=lambda item,index:'var(--chart-other)' if item['label']=='Khác' else palette[tty.get(item['label'],index)%len(palette)]
    used=0;parts=['<div class="ui-chart-caption"><span>Tỷ trọng dòng thuật ngữ đủ điều kiện</span><span>Tổng = 100%</span></div><div class="r4-pie-layout"><svg class="r4-donut" viewBox="0 0 230 230" role="img" aria-label="Cơ cấu TTY theo số thuật ngữ">']
    for index,item in enumerate(items):
        share=item['count']/total*100;info=f'{chart_number(item["count"])} thuật ngữ · {chart_number(item["pct"],2)}%'
        parts.append(f'<circle cx="115" cy="115" r="78" fill="none" stroke="{color(item,index)}" stroke-width="30" pathLength="100" stroke-dasharray="{share:.6f} {100-share:.6f}" stroke-dashoffset="{-used:.6f}" transform="rotate(-90 115 115)"{chart_tip(item["label"],info)}><title>{safe(item["label"])}: {chart_number(item["pct"],2)}%</title></circle>');used+=share
    parts.append(f'<text x="115" y="112" class="donut-title" text-anchor="middle">{chart_number(total)}</text><text x="115" y="134" class="donut-sub" text-anchor="middle">thuật ngữ</text></svg><div class="r4-legend">')
    for index,item in enumerate(items):parts.append(f'<div><i style="background:{color(item,index)}"></i><span>{safe(item["label"])}</span><strong>{chart_number(item["pct"],2)}%</strong></div>')
    return ''.join(parts)+'</div></div>'


def svg_scatter(rows):
    if not rows:return ""
    left=83;right=730;top=30;bottom=255;max_x=max(2,max(row['terms'] for row in rows));max_y=max(10,max(row['avg_name_length'] for row in rows))
    xscale=lambda value:left+(right-left)*math.log2(max(1,value))/math.log2(max_x);yscale=lambda value:bottom-(bottom-top)*value/max_y
    parts=['<div class="ui-chart-caption"><span>Y · Độ dài tên trung bình (ký tự)</span><span>Mỗi điểm = 1 RxCUI trong mẫu minh họa</span></div><svg class="r4-svg" viewBox="0 0 760 315" role="img" aria-label="Scatter: số thuật ngữ trên RxCUI và độ dài tên trung bình">']
    for tick in range(5):
        value=max_y*tick/4;y=yscale(value)
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" class="gridline"/><text x="{left-12}" y="{y+4:.1f}" text-anchor="end" class="ticks">{chart_number(value,0)}</text>')
    tick=1
    while tick<=max_x:
        x=xscale(tick);parts.append(f'<text x="{x:.1f}" y="{bottom+22}" text-anchor="middle" class="ticks">{tick}</text>');tick*=2
    for row in rows:
        label='RxCUI '+str(row['rxcui']);info=f'{row["terms"]} tên · Độ dài TB {chart_number(row["avg_name_length"],2)} ký tự'
        parts.append(f'<circle cx="{xscale(row["terms"]):.1f}" cy="{yscale(row["avg_name_length"]):.1f}" r="3.1" class="scatter-dot"{chart_tip(label,info)}><title>{safe(label)}: {safe(info)}</title></circle>')
    parts.append('<text x="400" y="306" text-anchor="middle" class="ticks">X · Số thuật ngữ / RxCUI (trục log₂)</text></svg>');return ''.join(parts)

def panel(index, kind, title, purpose, visual, conclusion):
    return (f'<article class="r4-chart-card"><div class="r4-chart-head"><span class="r4-number">{index:02d}</span><div><span class="r4-kind">{safe(kind)}</span><h3>{safe(title)}</h3><p>{safe(purpose)}</p></div></div>'+
            visual+f'<p class="r4-insight"><strong>Diễn giải:</strong> {safe(conclusion)}</p></article>')

def render_sections(d):
    name=d["name_length"];terms=d["terms_per_rxcui"]
    stats=[
        ("Số quan sát",fmt(name["n"])),
        ("Mean",fmt(name["mean"],2)),
        ("Median",fmt(name["median"],2)),
        ("Mode",fmt(name["mode"])),
        ("Variance",fmt(name["variance"],2)),
        ("Standard deviation",fmt(name["std_dev"],2)),
        ("Range",f'{name["min"]}–{name["max"]}'),
        ("Q1 / Q3",f'{name["q1"]:.1f} / {name["q3"]:.1f}')
    ]
    table='<div class="r4-stat-grid">'+''.join(f'<div class="r4-stat"><small>{safe(k)}</small><b>{safe(v)}</b></div>' for k,v in stats)+'</div>'
    css="""<style>
.r4-start{padding:26px 0 10px;border-top:1px solid #dfe7e8;margin-top:24px}.r4-start h2{font-size:32px;margin:7px 0;color:#163a49}.r4-overline{color:#0e877c;font-size:12px;text-transform:uppercase;font-weight:800;letter-spacing:2px}.r4-lead{max-width:870px}.r4-stat-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:20px 0 26px}.r4-stat{border:1px solid #deebeb;border-radius:13px;padding:14px;background:#fff}.r4-stat small{display:block;color:#68808c;font-size:11px}.r4-stat b{display:block;margin-top:8px;font-size:21px;color:#153f54}.r4-charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.r4-chart-card{background:#fff;border:1px solid #e0e8e9;border-radius:17px;padding:22px;min-width:0}.r4-chart-head{display:flex;gap:12px;align-items:start}.r4-number{width:37px;height:37px;border-radius:10px;background:#e5f4f0;color:#0b7c74;display:grid;place-items:center;font-weight:800;flex-shrink:0}.r4-kind{font-size:10px;text-transform:uppercase;font-weight:800;letter-spacing:1.2px;color:#129288}.r4-chart-head h3{margin:2px 0 3px;color:#173e4d;font-size:17px}.r4-chart-head p{margin:0 0 14px;font-size:12px}.r4-svg{width:100%;height:auto;max-height:360px}.gridline{stroke:#e9eff0;stroke-width:1}.ticks{font:11px system-ui,sans-serif;fill:#667d89}.column{fill:#17a098}.column:hover{fill:#0c736d}.box-fill{fill:#9fd4ca;stroke:#228e83;stroke-width:1.5}.whisker{stroke:#0b6c67;stroke-width:2}.median{stroke:#ed9059;stroke-width:3}.box-label{font:bold 12px system-ui,sans-serif;fill:#244858}.scatter-dot{fill:#0b8980;opacity:.36}.scatter-dot:hover{opacity:1;fill:#dc8650}.r4-pie-layout{display:flex;align-items:center;gap:10px}.r4-donut{width:48%;max-width:250px}.r4-legend{flex:1}.r4-legend div{display:flex;align-items:center;gap:8px;font-size:12px;margin:6px 0}.r4-legend i{width:10px;height:10px;flex-shrink:0;border-radius:3px}.r4-legend span{flex:1}.r4-legend strong{font-variant-numeric:tabular-nums}.donut-title{font:bold 29px system-ui,sans-serif;fill:#163e48}.donut-sub{font:11px system-ui,sans-serif;fill:#6b8187}.r4-insight{background:#f0f8f6;border-left:3px solid #1c938a;border-radius:5px;padding:11px 12px;font-size:12px!important;line-height:1.65;color:#3d5961!important}.r4-note{border:1px solid #e0e9e8;background:#f7faf9;padding:16px 20px;border-radius:15px;margin-top:15px;font-size:13px;color:#546874}.r4-note strong{color:#234855}@media(max-width:850px){.r4-charts{grid-template-columns:1fr}.r4-stat-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:480px){.r4-stat-grid{grid-template-columns:repeat(2,1fr)}.r4-chart-card{padding:14px}.r4-pie-layout{flex-direction:column}.r4-donut{width:70%}.r4-legend{width:100%}}
</style>"""
    group_totals=d["tty_distribution"][:10]
    top=group_totals[0]
    # Four classic course chart families + second frequency comparison.
    allpanels=[
        panel(1,"Bar / Column chart","Phân bố các loại thuật ngữ TTY","Biến phân loại → so sánh số lượng theo nhóm.",svg_bar(group_totals,"TTY groups","label","count"),f'{top["label"]} là nhóm nhiều nhất ({fmt(top["count"])} dòng). Cột thể hiện số thuật ngữ, không phải số thuốc khác nhau.'),
        panel(2,"Histogram","Phân bố độ dài tên thuốc / thuật ngữ","Biến định lượng độ dài display_name (ký tự) → histogram với các khoảng 10 ký tự.",svg_bar(d["histogram_name_length"],"Histogram length","bin","count"),f'Trung vị {chart_number(name["median"],1)} ký tự, trung bình {chart_number(name["mean"],1)}; quan sát độ lệch giữa hai chỉ số để nhận biết phân phối bất đối xứng.'),
        panel(3,"Box plot","Độ phân tán tên theo loại thuật ngữ","Đối chiếu median, Q1, Q3 và whiskers 1.5×IQR giữa 6 nhóm TTY nhiều nhất.",svg_boxplots(d["boxplot_by_tty"]),'Nhóm có hộp dài có biến thiên độ dài tên lớn hơn. Các giá trị ngoại lai không vẽ riêng; số lượng được tính trong dữ liệu thống kê.'),
        panel(4,"Pie / Doughnut chart","Cơ cấu các nhóm TTY","Biến phân loại → tỷ trọng top 6 nhóm so với phần còn lại.",svg_donut(d["tty_composition"]),'Tỷ lệ phần trăm tính trên tổng số dòng thuật ngữ đủ điều kiện mapping; không phải cơ cấu sản phẩm DAV.'),
        panel(5,"Histogram / Frequency","Số thuật ngữ trên mỗi RxCUI","Biến số đếm → tần suất RxCUI có 1, 2, 3, 4–5, 6–10, 11–20 hoặc ≥21 tên.",svg_bar(d["histogram_terms_per_rxcui"],"Term frequency","bin","count"),f'Có {fmt(d["n_rxcui"])} mã RxCUI; trung bình {chart_number(terms["mean"],2)} thuật ngữ/mã, trung vị {chart_number(terms["median"],1)}.'),
        panel(6,"Scatter plot","Số tên/RxCUI và độ dài tên trung bình","Hai biến định lượng trên mỗi RxCUI; hiển thị mẫu phân tầng có tính minh họa.",svg_scatter(d["scatter_illustrative"]),f'Tương quan Pearson trên TOÀN BỘ {fmt(d["n_rxcui"])} RxCUI = {chart_number(d["pearson_all_rxcui"],4) if d["pearson_all_rxcui"] is not None else "không xác định"}; các điểm chỉ là mẫu {d["scatter_sample_size"]} mã, không khẳng định quan hệ nhân quả.')
    ]
    return (css+'<section class="r4-start" id="report-4"><div class="r4-overline">Trực quan hóa thống kê · Statistical data visualization</div><h2>RxNorm dưới góc nhìn thống kê.</h2><p class="r4-lead">Áp dụng kiến thức Chương 6.1–6.4: thống kê mô tả, biến phân loại / định lượng, phân phối, so sánh, cơ cấu và mối quan hệ. Mỗi biểu đồ dùng dữ liệu RxNorm hiện hành, không dùng dữ liệu mô phỏng.</p></section>'+
            '<section><h2>Thống kê mô tả · Độ dài display_name</h2>'+table+'</section><div class="r4-charts">'+''.join(allpanels)+'</div>'+
            '<div class="r4-note"><strong>Lưu ý phương pháp:</strong> Mean/variance/SD tính theo toàn bộ bản ghi RxNorm hiện có (population, ddof=0). Q1/Q3 dùng nội suy tuyến tính. Box plot dùng whisker đến quan sát xa nhất trong ngưỡng 1.5×IQR. Không có nhiều mốc thời gian nên không tạo line chart diễn biến theo tháng, stacked chart theo thời gian hay suy diễn phân phối chuẩn / T-test. Ứng viên mapping vẫn phải được rà soát chuyên môn.</div>')

