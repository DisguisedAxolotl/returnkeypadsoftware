"""Lightweight CSV reader for the allowlist without the csv module.

CircuitPython builds often omit ``csv``, so this uses simple line splitting.
It looks up a row by the student ID column (default header name ``PIN``).
"""


def lookup_student(
    student_id,
    *,
    filename: str = "Allowlist.csv",
    id_column: str = "STUDENT_PIN",
):
    """Return the row matching ``student_id`` or ``None`` if not found.

    If the file has a header containing ``id_column``, a dict is returned.
    Otherwise a tuple of row strings is returned.
    """

    sid = str(student_id).strip()

    try:
        with open(filename, "r") as f:
            lines = f.read().splitlines()
    except OSError as err:
        print("Allowlist read failed:", err)
        return None

    if not lines:
        return None

    header = _split_line(lines[0])
    use_header = False
    id_idx = 0

    # Detect header presence by column name.
    if id_column in header:
        use_header = True
        id_idx = header.index(id_column)
        data_lines = lines[1:]
    else:
        data_lines = lines  # treat first line as data

    for raw in data_lines:
        row = _split_line(raw)
        if _row_matches(row, sid, id_idx):
            if use_header:
                padded = row + [""] * (len(header) - len(row))
                return dict(zip(header, padded))
            return tuple(row)

    return None


def _split_line(line: str):
    # Simple comma split; trims whitespace and ignores empty trailing columns.
    return [part.strip() for part in line.split(",")]


def _row_matches(row, student_id, idx):
    try:
        return row[idx] == student_id
    except IndexError:
        return False
