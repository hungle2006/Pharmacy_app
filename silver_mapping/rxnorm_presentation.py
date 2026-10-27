"""Data-backed, self-contained Report 3/4 reading and presentation experience."""
from html import escape
from pathlib import Path
import re

from silver_mapping.rxnorm_report3_formulas import (
    STYLE, quality_formulas, inferential_formulas, vi,
)
from silver_mapping.rxnorm_report4 import render_sections


def h(value):
    return escape(str(value), quote=True)


def table(headings, rows):
    return '<div class="table-wrap" tabindex="0"><table><thead><tr>' + ''.join(
        '<th scope="col">' + h(x) + '</th>' for x in headings
    ) + '</tr></thead><tbody>' + ''.join(
        '<tr>' + ''.join('<td>' + h(x) + '</td>' for x in row) + '</tr>' for row in rows
    ) + '</tbody></table></div>'


def note(text, title="Điều cần nhớ"):
    return '<div class="takeaway"><span>' + h(title) + '</span><p>' + h(text) + '</p></div>'


def detail(label, body):
    return '<details class="deep-dive"><summary>' + h(label) + '</summary><div class="detail-body">' + body + '</div></details>'


def cards(items):
    return '<div class="stat-grid">' + ''.join(
        '<div class="stat"><span>' + h(label) + '</span><strong>' + h(value) + '</strong><small>' + h(unit) + '</small></div>'
        for label, value, unit in items
    ) + '</div>'


def pvalue(value):
    if value is None:
        return 'Chưa đủ dữ liệu'
    if value == 0:
        return '<1e−300*'
    return f'{value:.3g}'


def render_presentation(report):
    e = report['report_3_eda']
    m = report['report_3_multivariate']
    s = report['report_4_statistics']
    name = s['name_length']
    coh = m['lexical_coherence']
    fs = inferential_formulas(m)
    # Reuse the established MathML cards and SVG charts; no altered calculations.
    quality = quality_formulas(e, m, s)
    qcards = re.findall(r'<article class="r3-formula">.*?</article>', quality, re.S)
    chart_html = render_sections(s)
    chart_style = re.search(r'<style>.*?</style>', chart_html, re.S).group()
    charts = re.findall(r'<article class="r4-chart-card">.*?</article>', chart_html, re.S)
    sections = []

    def step(id_, report_no, label, title, lead, body, speech):
        index = len(sections) + 1
        sections.append((id_, report_no, label,
            f'<section class="report-step" id="{id_}" data-report="{report_no}" aria-labelledby="{id_}-title">'
            f'<header class="step-heading"><span class="step-kicker">REPORT {report_no} <i>/</i> {index:02d}</span>'
            f'<h2 id="{id_}-title">{h(title)}</h2><p>{h(lead)}</p></header>' + body +
            '</section>'))

    total = e['total_rows']
    concepts = e['distinct_rxcui_mapping_ready']
    multiple = m['cross_column_quality']['concepts_with_multiple_names']
    multi_pct = 100 * multiple / concepts if concepts else 0
    step('overview', '3', 'Bối cảnh & câu hỏi', 'Trước khi ghép thuốc, hãy hiểu dữ liệu.',
         'Report 3 khám phá và kiểm tra RxNorm. Report 4 dùng biểu đồ để giải thích những gì đã tìm thấy.',
         '<div class="hero-statement">Một mã khái niệm.<br><em>Nhiều cách gọi tên.</em></div>' +
         cards([('Bản ghi nguồn', vi(total), 'dòng thuật ngữ'), ('RxCUI đủ điều kiện', vi(concepts), 'mã khái niệm khác nhau'),
                ('Loại thuật ngữ TTY', vi(m['cross_column_quality']['tty_unique_values']), 'nhóm phân loại'),
                ('RxCUI có nhiều tên', vi(multi_pct, 2) + '%', vi(multiple) + ' mã')]) +
         '<div class="question-grid"><div><b>01 · Dữ liệu là gì?</b><p>Mỗi dòng chứa một tên hoặc cách biểu diễn của một khái niệm RxNorm.</p></div>'
         '<div><b>02 · Có sử dụng được?</b><p>Kiểm tra thiếu, trùng, chuẩn hóa và điều kiện đưa vào mapping.</p></div>'
         '<div><b>03 · Thấy quy luật gì?</b><p>So sánh độ dài tên, loại thuật ngữ và sự nhất quán giữa các tên.</p></div></div>' +
         note('Số dòng thuật ngữ khác số khái niệm, và cả hai đều không phải số sản phẩm thuốc DAV.'),
         f'Nhóm thu thập được {vi(total)} dòng thuật ngữ. Sau khi kiểm tra điều kiện mapping, có {vi(concepts)} mã RxCUI. Vì một khái niệm có thể có nhiều tên, nhóm phân tích riêng ở cấp dòng thuật ngữ và cấp mã RxCUI.')

    dictionary = [
        ('rxcui', 'Mã khái niệm', 'Định danh', 'Gom các tên cùng một khái niệm; không tính trung bình giá trị mã.'),
        ('display_name', 'Tên hiển thị gốc', 'Văn bản', 'Đếm số ký tự và đọc nội dung thuật ngữ.'),
        ('normalized_name', 'Tên đã chuẩn hóa', 'Văn bản', 'So khớp văn bản sau khi bỏ khác biệt viết hoa, dấu, khoảng trắng.'),
        ('tty', 'Loại thuật ngữ', 'Phân loại', 'IN: hoạt chất; SCD: thuốc lâm sàng chuẩn; SBD: thuốc có thương hiệu.'),
        ('sab', 'Nguồn thuật ngữ', 'Phân loại', 'Phân biệt nguồn; snapshot này chỉ có RXNORM.'),
    ]
    derived = [('terms_per_rxcui', 'Số dòng thuật ngữ trên một RxCUI', 'Mức đa dạng cách biểu diễn'),
               ('avg_name_length', 'Độ dài tên trung bình trong một RxCUI', 'Mức dài/ngắn của tên'),
               ('max_name_length', 'Tên dài nhất trong một RxCUI', 'Nhận diện tên rất dài'),
               ('distinct_tty_per_rxcui', 'Số nhóm TTY khác nhau trên một RxCUI', 'Đa dạng loại thuật ngữ')]
    step('data-dictionary', '3', 'Hiểu từng cột', 'Chọn biến theo câu hỏi, không theo vị trí cột.',
         'RxCUI là nhãn định danh. Các phép toán thống kê dùng biến đo lường hoặc biến dẫn xuất có ý nghĩa.',
         table(['Cột gốc', 'Ý nghĩa', 'Thang đo', 'Mục đích phân tích'], dictionary) +
         detail('4 biến dẫn xuất dùng trong tương quan', table(['Biến', 'Cách tạo', 'Trả lời điều gì?'], derived)) +
         note('SAB chỉ có một giá trị nên không có biến thiên để phân tích liên hệ TTY × SAB.'),
         'Nhóm không lấy mã RxCUI đi tính tương quan. Thay vào đó, nhóm gom theo mã để tính số tên, độ dài trung bình và số loại TTY. Đây là các biến có ý nghĩa thống kê.')

    sample = e.get('sample_mapping_ready', [])
    sample_rows = [[x['rxcui'], x['tty'], x['display_name'], x['normalized_name']] for x in sample[:4]]
    step('data-quality', '3', 'Chất lượng & xử lý', 'Dữ liệu đủ điều kiện kỹ thuật đến đâu?',
         'Đối chiếu năm cột chính, kiểm tra khóa trùng và so tên chuẩn hóa với quy tắc đã công bố.',
         cards([('Đủ điều kiện mapping', vi(e['mapping_ready_rows']), vi(e['mapping_ready_rate_pct'], 2) + '% số dòng nguồn'),
                ('Dòng bị loại', vi(e['excluded_rows']), 'theo quy tắc hiện hành'),
                ('Lệch chuẩn hóa', vi(e['normalization_difference_rows']), 'so với quy tắc kiểm tra')]) +
         table(['Cột kiểm tra', 'Giá trị thiếu', 'Tỷ lệ'], [[x['field'], vi(x['count']), vi(x['percentage'], 2) + '%'] for x in e['missing_by_field']]) +
         '<div class="process"><span>Kiểm tra thiếu</span><b>→</b><span>Kiểm tra RxCUI / SAB</span><b>→</b><span>Loại khóa trùng</span><b>→</b><span>Mapping-ready</span></div>' +
         '<p class="body-copy">Khóa trùng: <code>(rxcui, tty, sab, display_name)</code>. Giữ nguyên tên gốc; chuẩn hóa một cột riêng bằng NFKD, bỏ dấu, chữ thường, thay dấu câu bằng khoảng trắng và gộp khoảng trắng.</p>' +
         detail('Xem công thức tỷ lệ & cách thay số', '<div class="r3-formula-grid">' + ''.join(qcards[:4]) + '</div>') +
         detail('Ví dụ bản ghi sau xử lý', table(['RxCUI', 'TTY', 'Tên gốc', 'Tên chuẩn hóa'], sample_rows)) +
         note('Đủ điều kiện kỹ thuật không có nghĩa các ứng viên ghép thuốc đã được xác minh lâm sàng.'),
         f'Có {vi(e["mapping_ready_rows"])} dòng đủ điều kiện đưa vào bước mapping. Đây là kiểm tra cấu trúc và chất lượng thuật ngữ; chưa phải đánh giá tính đúng đắn của một cặp thuốc được ghép.')

    step('descriptive', '3', 'Thống kê mô tả', 'Tên thuốc dài và phân tán như thế nào?',
         f'Biến được đo là số ký tự trong display_name, tính trên {vi(name["n"])} thuật ngữ đủ điều kiện mapping.',
         cards([('Trung bình · Mean', vi(name['mean'], 3), 'ký tự'), ('Trung vị · Median', vi(name['median']), 'ký tự'),
                ('Giá trị phổ biến · Mode', vi(name['mode']), 'ký tự'), ('Độ lệch chuẩn · Standard deviation', vi(name['std_dev'], 3), 'ký tự')]) +
         table(['Chỉ số', 'Giá trị', 'Cách hiểu'], [
             ('Phương sai σ²', vi(name['variance'], 3) + ' ký tự²', 'Trung bình bình phương độ lệch so với độ dài tên trung bình.'),
             ('Nhỏ nhất / lớn nhất', f'{vi(name["min"])} / {vi(name["max"])} ký tự', 'Khoảng từ tên ngắn nhất đến tên dài nhất.'),
             ('Q1 / Q3', f'{vi(name["q1"])} / {vi(name["q3"])} ký tự', '50% phần giữa của dữ liệu nằm trong khoảng này.'),
             ('IQR', vi(name['iqr']) + ' ký tự', 'Độ rộng của 50% phần giữa: Q3 − Q1.')]) +
         note('σ² phản ánh mức phân tán của ĐỘ DÀI TÊN. Căn bậc hai của σ² là SD, có đơn vị ký tự nên dễ diễn giải hơn. SD không phải độ lệch của mọi tên và không suy ra 68% dữ liệu khi chưa biết phân phối.') +
         detail('Xem công thức trung bình, phương sai & độ lệch chuẩn', '<div class="r3-formula-grid">' + ''.join(qcards[4:]) + '</div>'),
         f'Tên có độ dài trung bình {vi(name["mean"], 2)} ký tự, trong khi trung vị là {vi(name["median"])}. Sự chênh lệch này gợi ý phân bố kéo dài về phía tên dài. Độ lệch chuẩn {vi(name["std_dev"], 2)} ký tự cho thấy độ dài không đồng đều; biểu đồ ở Report 4 sẽ giúp nhìn rõ hơn.')

    labels = {'terms_per_rxcui': 'Số tên / RxCUI', 'avg_name_length': 'Độ dài tên TB', 'max_name_length': 'Độ dài tên lớn nhất', 'distinct_tty_per_rxcui': 'Số loại TTY / RxCUI'}
    corr_rows = [[labels[q['x']], labels[q['y']], vi(q['n']), vi(q['pearson_r'], 4), vi(q['spearman_rho'], 4)] for q in m['correlations']]
    first_corr = m['correlations'][0]
    step('r3-correlation', '3', 'Pearson & Spearman', 'Mã có nhiều tên có đi cùng tên dài hơn?',
         'Đơn vị phân tích: mỗi RxCUI xuất hiện một lần. Pearson xét tuyến tính; Spearman xét xu hướng theo thứ hạng.',
         table(['Biến X', 'Biến Y', 'N RxCUI', 'Pearson r', 'Spearman ρ'], corr_rows) +
         '<div class="question-grid two"><div><b>Pearson trả lời</b><p>Khi X tăng, Y có tăng gần theo một đường thẳng không?</p></div>'
         '<div><b>Spearman trả lời</b><p>RxCUI có thứ hạng X cao hơn có thường có thứ hạng Y cao hơn không?</p></div></div>' +
         note(f'Cặp số tên–độ dài trung bình có Pearson r = {vi(first_corr["pearson_r"], 4)} và Spearman ρ = {vi(first_corr["spearman_rho"], 4)}. Trong snapshot này, xu hướng đồng biến theo hạng rõ hơn mối quan hệ tuyến tính.', 'Đọc kết quả thực tế') +
         detail('Vì sao phải rank X và rank Y? · Ví dụ minh họa',
                '<p>Thay giá trị mỗi biến bằng vị trí của nó trong dãy đã sắp xếp, rồi tính tương quan giữa hai dãy hạng. Giá trị bằng nhau nhận trung bình các vị trí hạng.</p>' +
                table(['Mã minh họa', 'X: số tên', 'Rank X', 'Y: độ dài TB', 'Rank Y'], [('A', 1, 1, 20, 1), ('B', 2, 2.5, 50, 3), ('C', 2, 2.5, 30, 2), ('D', 4, 4, 70, 4)]) +
                '<p>Đây là ví dụ giải thích cách xếp hạng, không phải mẫu được dùng để tính hệ số trong báo cáo.</p>') +
         detail('Xem công thức Pearson / Spearman', fs['correlation']) +
         note('Số loại TTY không thể vượt số dòng tên nên tương quan giữa hai biến này có phần liên hệ cấu trúc. Không coi hệ số cao là khám phá lâm sàng hay bằng chứng nhân quả.'),
         'Ở cặp số tên và độ dài trung bình, nhóm xem cả Pearson và Spearman để phân biệt quan hệ tuyến tính với xu hướng đồng biến theo hạng. Không dùng các hệ số này để kết luận số tên gây ra tên dài hơn.')

    ttests = m['welch_t_tests']
    trows = [[q['comparison'], vi(q['n_a']), vi(q['n_b']), vi(q.get('mean_a'), 3), vi(q.get('mean_b'), 3), vi(q.get('t'), 4), vi(q.get('cohen_d'), 3)] for q in ttests]
    step('r3-welch', '3', 'Welch t-test', 'Độ dài tên có khác giữa các nhóm TTY?',
         'So sánh trung bình hai nhóm bằng Welch, không yêu cầu phương sai hai nhóm bằng nhau.',
         table(['So sánh A − B', 'nA', 'nB', 'Mean A', 'Mean B', 't', 'Cohen d'], trows) +
         '<div class="question-grid two"><div><b>nA và nB là gì?</b><p>Số RxCUI độc lập được dùng trong từng nhóm sau khi loại mã xuất hiện ở cả hai nhóm. Không phải số lần kiểm định.</p></div>'
         '<div><b>Dấu âm của t và d?</b><p>Với cách lấy A − B, dấu âm cho biết trung bình nhóm A thấp hơn nhóm B. |d| thể hiện độ lớn khác biệt.</p></div></div>' +
         detail('Công thức t, bậc tự do, Cohen d và khoảng tin cậy', fs['ttest']) +
         detail('Số liệu chi tiết cho từng cặp so sánh', table(['So sánh', 'df', 'Hiệu số A − B', 'CI 95% xấp xỉ chuẩn', 'RxCUI chung bị loại', 'Trạng thái'], [
             [q['comparison'], vi(q.get('df'), 2), vi(q.get('difference'), 3),
              ' đến '.join(vi(v, 3) for v in q.get('ci95_normal_approx', [])) or 'Chưa đủ dữ liệu',
              vi(q.get('overlapping_rxcui_excluded', 0)), q['status']] for q in ttests])) +
         note('Ở so sánh SY–PSN, các mã thuộc đồng thời hai nhóm đã bị loại. Kết quả chỉ áp dụng cho tập mã còn lại, không tự động đại diện toàn bộ SY và PSN.'),
         'Welch giúp trả lời độ dài tên trung bình có khác giữa hai loại thuật ngữ hay không. Nhóm đọc thêm Cohen d để xem khác biệt lớn đến đâu, vì p rất nhỏ chưa chắc đi cùng khác biệt lớn trong thực tế.')

    prows = [[q['comparison'], pvalue(q.get('p_value')), pvalue(q.get('p_holm')), 'Có bằng chứng khác biệt' if q.get('p_holm') is not None and q['p_holm'] < .05 else 'Chưa kết luận khác biệt'] for q in ttests]
    step('p-holm', '3', 'p-value & p-Holm', 'p nhỏ trả lời điều gì, và không trả lời điều gì?',
         'H₀: độ dài tên trung bình của hai nhóm bằng nhau. Mức ý nghĩa được đọc tại α = 0,05.',
         '<div class="definition"><b>p-value</b><p>Giả sử H₀ và các giả định kiểm định đúng, xác suất thu được thống kê kiểm định cực đoan ít nhất như kết quả đã quan sát là bao nhiêu?</p>'
         '<div class="math-line">p = 2 × [1 − F<sub>t,ν</sub>(|t<sub>quan sát</sub>|)]</div>'
         '<small>Kiểm định Welch hai phía: F là hàm phân phối tích lũy của phân phối t với bậc tự do ν.</small></div>' +
         table(['So sánh', 'p gốc', 'p-Holm', 'Đọc tại α = 0,05'], prows) +
         '<p class="fine-print">* Giá trị lưu bằng 0 do giới hạn số học được hiển thị &lt;1e−300, không phải xác suất bằng 0.</p>' +
         detail('Holm tính như thế nào?',
                '<ol><li>Xếp các p gốc tăng dần.</li><li>Với m phép thử, nhân p ở vị trí i với (m − i + 1).</li><li>Lấy cực đại lũy tích và chặn tại 1, rồi trả về thứ tự so sánh ban đầu.</li></ol>' +
                '<p>Trong báo cáo có 3 cặp so sánh. Ở cặp SCD–SBD, p đứng thứ hai nên hệ số là 2; kết quả còn phải tuân quy tắc cực đại lũy tích. Hiệu chỉnh giúp kiểm soát nguy cơ kết luận dương tính giả trên cả nhóm phép thử.</p>') +
         note('p không phải xác suất H₀ đúng, không phải tỷ lệ dữ liệu sai, và p-Holm không phải phần trăm tin cậy. Kết luận phải đi cùng độ lớn hiệu ứng và các giả định.'),
         'Nhóm đặt giả thuyết ban đầu là trung bình hai nhóm bằng nhau. p đo mức độ bất thường của kết quả dưới giả thuyết đó. Vì thực hiện ba so sánh, nhóm đọc p đã hiệu chỉnh Holm để hạn chế kết luận khác biệt do thử nhiều lần.')

    chi = m['chi_square']
    chi_rows = [[label] + [vi(v) for v in row] for label, row in zip(chi['row_labels'], chi['observed'])]
    step('r3-chi2', '3', 'Chi-square & Cramér V', 'Loại TTY có liên hệ với nhóm độ dài tên?',
         'Lập bảng chéo giữa biến phân loại TTY và các khoảng độ dài tên. H₀: hai biến độc lập.',
         cards([('Chi-square χ²', vi(chi['statistic'], 3), 'chênh lệch quan sát so với kỳ vọng'),
                ('Bậc tự do df', vi(chi['df']), '(số hàng − 1) × (số cột − 1)'),
                ('Cramér V', vi(chi['cramers_v'], 3), 'độ mạnh liên hệ từ 0 đến 1')]) +
         table(['TTY / ký tự'] + chi['column_labels'], chi_rows) +
         detail('Công thức, tần số kỳ vọng & thay số', fs['chi']) +
         note('Một RxCUI có thể có nhiều dòng thuật ngữ nên giả định các quan sát độc lập chưa hoàn toàn đáp ứng. Xem p như tín hiệu khám phá; ưu tiên bảng phân bố và Cramér V khi diễn giải.'),
         'Bảng chéo cho thấy các loại TTY phân bố khác nhau giữa các khoảng độ dài tên. Cramér V mô tả độ mạnh liên hệ. Do các tên có thể chung RxCUI, nhóm không dùng p của bảng này để khẳng định chắc chắn một quan hệ tổng quát.')

    step('r3-coherence', '3', 'Coherence / Jaccard', 'Các tên chung RxCUI giống nhau về từ vựng đến đâu?',
         'Tách tên thành tập token. Đối chiếu tối đa 15 tên với tên tham chiếu đầu tiên trong mỗi RxCUI.',
         cards([('RxCUI có thể so sánh', vi(coh['n_comparable_rxcui']), 'mã có nhiều tên'),
                ('Jaccard trung bình', vi(coh['mean'], 3), 'trung bình theo mã có thể so sánh'),
                ('Jaccard trung vị', vi(coh['median'], 3), 'mức giữa của phân bố')]) +
         table(['Mức trùng từ', 'Số RxCUI', 'Tỷ trọng'], [[x['label'], vi(x['count']), vi(100*x['count']/coh['n_comparable_rxcui'], 2) + '%'] for x in coh['distribution']] if coh['n_comparable_rxcui'] else []) +
         detail('Công thức Jaccard và ví dụ minh họa', fs['coherence']) +
         note('Coherence ở đây là nhất quán từ vựng. Tên ít trùng từ có thể do viết tắt, thương hiệu hoặc cách gọi khác; không tự động là dữ liệu sai.'),
         'Nhóm đo mức giao nhau của các từ giữa các tên cùng mã. Điểm thấp giúp chọn trường hợp cần rà soát. Đây không phải kiểm định độ tin cậy thang đo và cũng không xác nhận tương đương điều trị.')

    step('report-3-summary', '3', 'Kết luận Report 3', 'Từ số liệu đến quyết định xử lý.',
         'Mỗi kết quả cần dẫn đến một hành động cụ thể trước khi ghép DAV với RxNorm.',
         table(['Phát hiện', 'Ý nghĩa', 'Quyết định xử lý'], [
             (f'{vi(e["mapping_ready_rate_pct"], 2)}% dòng đủ điều kiện', 'Đạt quy tắc kỹ thuật hiện hành', 'Chuyển sang tạo ứng viên mapping.'),
             (f'{vi(multi_pct, 2)}% RxCUI có nhiều tên', 'Nhiều biểu diễn cho một khái niệm', 'Giữ tên hợp lệ; không loại chỉ vì trùng RxCUI.'),
             ('Độ dài tên phân tán', 'So tên thô dễ bị ảnh hưởng bởi cách biểu diễn', 'Dùng tên chuẩn hóa; đối chiếu thêm cấu trúc thuốc.'),
             ('TTY liên quan đến độ dài tên', 'Không nên coi mọi loại tên là đồng nhất', 'Phân biệt IN, SCD, SBD khi chọn đối tượng ghép.'),
             ('Một số mã có coherence thấp', 'Cần kiểm tra khác biệt cách viết', 'Ưu tiên rà soát, không xóa tự động.')]) +
         detail('Vì sao không dùng mọi phép kiểm định?', table(['Phép thử', 'Lý do không áp dụng'], [(q['test'], q['reason']) for q in m['not_applicable']])) +
         note('Report 3 trả lời dữ liệu là gì, chất lượng đến đâu và khác nhau ở điểm nào. Report 4 sẽ làm các kết quả đó dễ nhìn bằng biểu đồ.'),
         'Sau EDA, nhóm giữ các tên hợp lệ, phân biệt loại thuật ngữ và chuẩn bị tập dữ liệu đủ điều kiện mapping. Các kiểm định phục vụ hiểu dữ liệu, không thay thế bước xác minh chuyên môn.')

    step('report-4', '4', 'Chọn biểu đồ', 'Cùng một dữ liệu, mỗi biểu đồ trả lời một câu hỏi.',
         'Report 4 · Data Visualization — vận dụng nội dung thống kê mô tả và trực quan hóa của Chương 6.1–6.4.',
         '<div class="visual-index">' + ''.join(f'<a href="#chart-{i+1}"><span>0{i+1}</span><b>{h(k)}</b><small>{h(q)}</small></a>' for i, (k,q) in enumerate([
             ('Bar chart', 'Loại TTY nào có nhiều thuật ngữ?'), ('Histogram', 'Độ dài tên tập trung ở đâu?'),
             ('Box plot', 'Nhóm nào có tên phân tán hơn?'), ('Doughnut chart', 'Mỗi nhóm chiếm tỷ trọng bao nhiêu?'),
             ('Frequency chart', 'Một mã thường có bao nhiêu tên?'), ('Scatter plot', 'Số tên và độ dài tên liên hệ ra sao?')])) + '</div>' +
         note('Bar chart so sánh nhóm rời rạc; histogram biểu diễn khoảng của biến số. Chưa có chuỗi thời gian nên không vẽ xu hướng theo tháng.'),
         'Nhóm chọn biểu đồ theo câu hỏi và thang đo: phân loại dùng bar hoặc doughnut, phân bố số dùng histogram hoặc box plot, hai biến số dùng scatter. Mỗi biểu đồ đều ghi rõ đơn vị quan sát.')

    chart_guides = [
        ('Cơ cấu loại thuật ngữ', 'TTY nào xuất hiện nhiều nhất?', 'Đọc trục ngang là nhóm TTY, trục dọc là số dòng. Chỉ hiển thị 10 nhóm có nhiều thuật ngữ nhất; không coi tổng các cột là toàn bộ 22 nhóm.', 'Số thuật ngữ theo TTY', 'Biểu đồ cột cho phép so sánh số lượng tên giữa các loại thuật ngữ. Nhóm có cột cao nhất có nhiều dòng nhất, không có nghĩa là có nhiều sản phẩm thuốc nhất.'),
        ('Phân bố độ dài tên', 'Tên thường ngắn hay dài?', 'Trục ngang là khoảng độ dài, mỗi khoảng thông thường rộng 10 ký tự. Cột 100+ gom toàn bộ phần đuôi từ 100 ký tự trở lên nên không so mật độ trực tiếp với các khoảng rộng 10.', 'Số ký tự / dòng thuật ngữ', f'Trung bình {vi(name["mean"], 2)} cao hơn trung vị {vi(name["median"])}. Kết hợp hình dạng histogram, nhóm xem xét phần đuôi tên dài. Nhóm không mặc định dữ liệu tuân theo phân phối chuẩn.'),
        ('Độ phân tán giữa nhóm', 'Tên của nhóm TTY nào biến động nhiều hơn?', 'Mỗi hộp chứa 50% phần giữa: Q1 đến Q3. Vạch bên trong là trung vị; râu đến quan sát xa nhất trong ngưỡng 1,5 × IQR. Điểm ngoại lai chưa được vẽ riêng.', 'Độ dài tên theo TTY', 'So sánh vị trí trung vị để biết tên nhóm nào thường dài hơn; so độ rộng hộp để biết mức phân tán ở phần giữa. Ngoại lai là tín hiệu rà soát, không mặc định dữ liệu lỗi.'),
        ('Tỷ trọng các nhóm', 'Mỗi nhóm chiếm bao nhiêu phần trăm?', 'Doughnut dùng 6 nhóm đứng đầu và phần còn lại. Mẫu số là tổng dòng thuật ngữ đủ điều kiện mapping; các phần cộng lại thành 100% sau sai số làm tròn.', 'Tỷ lệ / dòng thuật ngữ', 'Biểu đồ tròn thể hiện cơ cấu trong toàn bộ thuật ngữ được phân tích. Phần Khác gom các nhóm còn lại, không phải dữ liệu thiếu.'),
        ('Số tên trên mỗi mã', 'Một RxCUI thường có bao nhiêu tên?', 'Đơn vị đếm đã đổi sang RxCUI: cột 1 là số mã chỉ có một tên. Các khoảng 4–5, 6–10… gom nhiều giá trị nên đây là tần suất nhóm, không so mật độ như khoảng có bề rộng bằng nhau.', 'Số RxCUI theo số thuật ngữ', f'Có {vi(multiple)} mã có nhiều tên, tương đương {vi(multi_pct, 2)}%. Đây là lý do không thể xóa tất cả các dòng trùng RxCUI.'),
        ('Mối liên hệ giữa hai biến', 'Có nhiều tên thì tên trung bình dài hơn không?', f'Mỗi điểm là một RxCUI trong mẫu minh họa phân tầng gồm {vi(s["scatter_sample_size"])} mã; trục X dùng log₂. Hệ số Pearson tính trên toàn bộ {vi(s["n_rxcui"])} RxCUI, không chỉ các điểm được vẽ.', 'Số tên và độ dài TB / RxCUI', 'Scatter giúp quan sát xu hướng, độ phân tán và những mã nổi bật. Không suy ra quan hệ nhân quả; đọc cùng Pearson và Spearman ở Report 3.'),
    ]
    for i, (label, title, reading, unit, speech) in enumerate(chart_guides):
        step(f'chart-{i+1}', '4', label, title, unit,
             charts[i] + '<div class="chart-reading"><span>CÁCH ĐỌC BIỂU ĐỒ</span><p>' + h(reading) + '</p></div>' +
             (detail('Bảng số liệu đầy đủ · tất cả nhóm TTY', table(['TTY', 'Số dòng'], [[x['label'], vi(x['count'])] for x in s['tty_distribution']])) if i == 0 else '') +
             (detail('Số liệu dùng trong box plot', table(['TTY', 'n', 'Q1', 'Median', 'Q3', 'Ngoại lai'], [[x['tty'], vi(x['n']), vi(x['q1'], 1), vi(x['median'], 1), vi(x['q3'], 1), vi(x['outliers'])] for x in s['boxplot_by_tty']])) if i == 2 else ''),
             speech)

    handoff = report['mapping_handoff']
    dist = handoff.get('mapping_status_distribution', [])
    examples = handoff.get('candidate_examples', [])
    step('conclusion', '4', 'Tổng kết & mapping', 'Hiểu dữ liệu trước, tạo ứng viên sau.',
         'Report 3 giải thích dữ liệu và kiểm định. Report 4 giúp người nghe nhìn thấy bằng chứng.',
         '<div class="process"><span>RxNorm Silver</span><b>→</b><span>EDA & QC</span><b>→</b><span>Mapping-ready</span><b>→</b><span>Ứng viên DAV ↔ RxNorm</span></div>' +
         '<div class="question-grid"><div><b>Giữ đúng đơn vị</b><p>Phân biệt dòng thuật ngữ, mã RxCUI và sản phẩm DAV.</p></div>'
         '<div><b>Đọc đúng thống kê</b><p>Đọc p cùng hiệu ứng; xem hình dạng phân bố trước khi kết luận.</p></div>'
         '<div><b>Ghép có kiểm chứng</b><p>Đối chiếu hoạt chất, hàm lượng và dạng bào chế; rà soát ứng viên.</p></div></div>' +
         (detail('Kết quả bước tạo ứng viên DAV ↔ RxNorm', '<p>Các số bên dưới thuộc tập bản ghi DAV trong bước mapping, có mẫu số khác với bảng RxNorm.</p>' + table(['Trạng thái', 'Số bản ghi DAV'], [[x['label'], vi(x['count'])] for x in dist]) +
                 table(['Tên DAV', 'RxCUI ứng viên', 'Tên RxNorm', 'Trạng thái'], [[x['dav_drug_name'], x['candidate_scd_rxcui'], x['candidate_scd_name'], x['mapping_status']] for x in examples])) if dist else '') +
         note('Ứng viên mapping chưa phải kết quả xác minh lâm sàng. Tương đồng tên, tương quan và Jaccard đều không chứng minh tương đương điều trị.'),
         'Hai báo cáo tạo cơ sở để hiểu và sử dụng dữ liệu RxNorm đúng cách. Sau đó nhóm tạo ứng viên ghép với DAV và đối chiếu thêm cấu trúc thuốc. Kết quả tự động vẫn cần rà soát chuyên môn.')

    nav = ''
    for report_no in ('3', '4'):
        nav += f'<div class="nav-group" data-report="{report_no}"><span>REPORT {report_no} · {"KHÁM PHÁ DỮ LIỆU" if report_no == "3" else "TRỰC QUAN HÓA"}</span>'
        for index, (id_, rn, label, _) in enumerate(sections):
            if rn == report_no:
                nav += f'<a href="#{id_}" data-step="{id_}"><small>{index+1:02d}</small>{h(label)}</a>'
        nav += '</div>'
    root = Path(__file__).parent
    css = (root / 'rxnorm_presentation.css').read_text(encoding='utf-8')
    js = (root / 'rxnorm_presentation.js').read_text(encoding='utf-8')
    assets = root.parent / 'assets'
    common_css = (assets / 'design-system.css').read_text(encoding='utf-8')
    research_css = (assets / 'research.css').read_text(encoding='utf-8')
    chart_js = (assets / 'chart-system.js').read_text(encoding='utf-8')
    return ('<!doctype html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
        '<script>if(!new URLSearchParams(location.search).has("detail")&&!location.hash)location.replace("/?view=reports");</script><meta name="description" content="Report 3–4 RxNorm: khám phá dữ liệu, công thức, kiểm định và biểu đồ có lời giải thích và nguồn dữ liệu.">' +
        '<title>RxNorm · Report 3 & 4 | PharmaBiz</title>' + STYLE + chart_style + '<style>' + css + common_css + research_css + '</style></head><body class="report-page">' +
        '<a href="#main" class="skip-link">Đến nội dung</a><header class="topbar"><a class="brand" href="/" aria-label="PharmaBiz trang chủ"><span class="brand-icon">P<span>+</span></span><b>PharmaBiz<small>DATA RESEARCH</small></b></a>' +
        '<div class="report-switch" role="group" aria-label="Chọn báo cáo"><button data-filter="all" aria-pressed="true">Tất cả</button><button data-filter="3" aria-pressed="false">Report 3</button><button data-filter="4" aria-pressed="false">Report 4</button></div>' +
        '<div class="top-actions"><button class="ui-theme-button" data-ui-theme aria-label="Chuyển giao diện sáng/tối">☾</button><button id="present-toggle" class="primary" aria-pressed="false">Trình chiếu <span>↗</span></button></div></header>' +
        '<button id="menu-toggle" aria-expanded="false" aria-controls="sidebar">☰ Mục lục</button><aside id="sidebar"><div class="sidebar-title"><span>RXNORM STUDY</span><h1>Hiểu dữ liệu.<br>Đọc bằng chứng.</h1><p>Report 3 & 4</p></div><nav aria-label="Mục lục báo cáo">' + nav +
        '</nav><div class="sidebar-footer"><a href="/?view=overview">← Tổng quan thị trường</a><a href="/disease-lookup.html">Tra cứu bệnh ↗</a><span class="status-dot"></span> Snapshot có nguồn kiểm chứng<br><small>Dữ liệu Silver · RxNorm</small></div></aside>' +
        '<main id="main" tabindex="-1"><div class="page-intro"><div><span class="eyebrow">RXNORM / RESEARCH REPORT</span><p>Khám phá dữ liệu → Trực quan hóa → Mapping</p></div><button id="print-report">In / lưu PDF</button></div>' +
        ''.join(x[3] for x in sections) +
        '<footer class="provenance"><b>Nguồn & phương pháp</b><p>Dữ liệu ' + h(report['source']) + ' · Kết xuất ' + h(report['generated_utc']) +
        '</p><details><summary>Xem SHA-256 và giới hạn phương pháp</summary><p class="hash">' + h(report['source_sha256']) +
        '</p><p>Thống kê mô tả tính trên snapshot sẵn có (phương sai tổng thể, ddof=0). Q1/Q3 nội suy tuyến tính. Biểu đồ dùng bản ghi đủ điều kiện mapping. Không có chuỗi thời gian. Kiểm định mang tính khám phá; không diễn giải nhân quả.</p></details></footer></main>' +
        '<div class="bottom-controls"><div class="progress-track"><span id="progress-fill"></span></div><div class="bottom-content"><div><span id="current-report">REPORT 3</span><b id="current-title">Bối cảnh & câu hỏi</b></div>' +
        '<div class="step-controls"><button id="prev-step" aria-label="Chủ đề trước">← <span>Trước</span></button><output id="step-counter" aria-live="polite">01 / ' + str(len(sections)) + '</output><button id="next-step" aria-label="Chủ đề tiếp theo"><span>Tiếp</span> →</button><button id="fullscreen-toggle" title="Toàn màn hình" aria-label="Toàn màn hình">⛶</button></div></div></div>' +
        '<div id="toast" role="status"></div><script>' + chart_js + ';PharmaCharts.installTooltips();' + js + '</script></body></html>')
