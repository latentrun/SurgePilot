from io import BytesIO

from app.services.run_reports import (
    FINAL_STATS_TOTAL_ROW_MISSING,
    FINAL_STATS_TOO_LARGE,
    parse_final_stats_csv,
)


def test_final_stats_parser_derives_kpis_from_the_total_row() -> None:
    result = parse_final_stats_csv(
        BytesIO(
            b"label,throughput,succ,fail,avg_rt,perc_90.0,perc_95.0,perc_99.0,rc_200,rc_500\n"
            b",1200,1188,12,0.1532,0.420,0.610,0.950,1188,12\n"
            b"GET /checkout,400,396,4,0.1884,0.500,0.700,0.980,396,4\n"
        )
    )

    assert result.parse_status == "parsed"
    assert result.summary_json["total"] == {
        "label": None,
        "totalRequests": 1200,
        "successRequests": 1188,
        "failedRequests": 12,
        "errorRate": 0.01,
        "averageResponseTimeMs": 153.2,
        "p90Ms": 420.0,
        "p95Ms": 610.0,
        "p99Ms": 950.0,
        "responseCodeCounts": {"200": 1188, "500": 12},
    }
    assert "throughputPerSecond" not in result.summary_json["total"]


def test_final_stats_parser_fails_closed_and_bounds_preview_rows() -> None:
    result = parse_final_stats_csv(
        BytesIO(b"label,throughput,succ,fail\nGET /only,1,1,0\n")
    )
    assert result.parse_status == "failed"
    assert result.parse_error_code == FINAL_STATS_TOTAL_ROW_MISSING

    rows = ["label,throughput,succ,fail,avg_rt"]
    rows.append(",5,4,1,0.1")
    rows.extend(f"GET /{index},1,1,0,0.1" for index in range(5))
    bounded = parse_final_stats_csv(BytesIO("\n".join(rows).encode()), max_rows=2)
    assert bounded.parse_status == "parsed"
    assert bounded.truncated is True
    assert len(bounded.summary_json["rows"]) == 2


def test_final_stats_parser_rejects_oversized_input_without_partial_parse() -> None:
    result = parse_final_stats_csv(BytesIO(b"x" * 11), max_bytes=10)
    assert result.parse_status == "failed"
    assert result.parse_error_code == FINAL_STATS_TOO_LARGE
