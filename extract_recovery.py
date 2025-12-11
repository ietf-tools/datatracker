import sys

# The order of these tables is important, as it determines the order in which they are restored.
TARGET_TABLES = [
    "datatracker.person_email",
    "datatracker.doc_document",
    "datatracker.doc_docevent",
    "datatracker.community_communitylist_added_docs",
    "datatracker.community_searchrule_name_contains_index",
    "datatracker.doc_ballotdocevent",
    "datatracker.doc_ballotpositiondocevent",
    "datatracker.doc_consensusdocevent",
    "datatracker.doc_docextresource",
    "datatracker.doc_dochistory",
    "datatracker.doc_dochistory_formal_languages",
    "datatracker.doc_dochistory_states",
    "datatracker.doc_dochistory_tags",
    "datatracker.doc_dochistoryauthor",
    "datatracker.doc_docreminder",
    "datatracker.doc_document_formal_languages",
    "datatracker.doc_document_states",
    "datatracker.doc_document_tags",
    "datatracker.doc_documentauthor",
    "datatracker.doc_documenturl",
    "datatracker.doc_lastcalldocevent",
    "datatracker.doc_newrevisiondocevent",
    "datatracker.doc_relateddochistory",
    "datatracker.doc_relateddocument",
    "datatracker.doc_statedocevent",
    "datatracker.doc_telechatdocevent",
    "datatracker.doc_writeupdocevent",
    "datatracker.ipr_iprdocrel",
    "datatracker.message_message_related_docs",
    "datatracker.review_reviewrequest",
    "datatracker.review_reviewassignment",
    "datatracker.doc_reviewassignmentdocevent",
    "datatracker.doc_reviewrequestdocevent",
    "datatracker.submit_submission",
    "datatracker.doc_submissiondocevent",
    "datatracker.submit_submission_formal_languages",
    "datatracker.submit_submissioncheck",
    "datatracker.submit_submissionevent",
]

# PKs identified by examining diffs between dumps before/after deleting email address
DELETED_REVIEWASSIGNMENTS = [
    11672,
    11613,
    11611,
    11610,
    11608,
    11607,
    11606,
    11605,
    11604,
    10723,
    10718,
    10706,
    10679,
    10676,
    10675,
    10673,
    10461,
    10454,
    9881,
    9852,
    9851,
    9513,
    9249,
    9248,
    9247,
    8381,
    8380,
    8368,
    8326,
    8315,
    8306,
    7919,
    7715,
    7655,
    7643,
    7630,
    7476,
    7475,
    7473,
    7445,
    7437,
    7431,
    7366,
    7329,
    7328,
    7325,
    7322,
    7275,
    7090,
    6694,
    5794,
    5472,
    5411,
    5126,
    2248,
    2229,
    1896,
    1631,
]

# PKs identified by examining diffs between dumps before/after deleting email address
DELETED_REVIEWREQUESTS = [
    13571,
    13570,
    13499,
    13493,
    13490,
    13487,
    13486,
    12291,
    12244,
    12240,
    12224,
    12199,
    12190,
    12184,
    11994,
    11898,
    11889,
    11875,
    11874,
    11254,
    11206,
    11205,
    10817,
    10670,
    10235,
    10234,
    10233,
    9080,
    9061,
    8969,
    8968,
    8938,
    8927,
    8883,
    8866,
    8857,
    8299,
    8023,
    7992,
    7978,
    7909,
    7897,
    7884,
    7863,
    7627,
    7626,
    7624,
    7613,
    7596,
    7588,
    7582,
    7516,
    7478,
    7477,
    7474,
    7471,
    7422,
    7223,
    6823,
    5902,
    5576,
    5516,
    2260,
    2241,
    1905,
    1639,
]


def main(source_file, target_file):
    source_lines = open(source_file, "r").readlines()
    table_in_progress = None
    tables = {}
    for line in source_lines:
        if any([
            not line.startswith("< "),
            line.startswith("< \\restrict"),
            line.startswith("< \\unrestrict"),
            line.startswith("< SELECT"),
        ]):
            continue
        if table_in_progress is None:
            assert(line.startswith("< COPY"))
            table_in_progress = line.split()[2]
            rows_in_progress = [line[2:]]
        elif line.startswith("< COPY"):
            if len(rows_in_progress) > 1:
                tables[table_in_progress] = rows_in_progress
            table_in_progress = line.split()[2]
            rows_in_progress = [line[2:]]
        else:
            rows_in_progress.append(line[2:])
    assert len(TARGET_TABLES) == 38
    assert set(TARGET_TABLES) == set(tables.keys())
    with open(target_file, "w") as f:
        for table in TARGET_TABLES:
            f.writelines(tables[table])
            f.write("\\.\n\n")
        # add simplehistory fixup
        f.write(
            "DELETE FROM datatracker.person_historicalemail WHERE "
            "address = 'shares@ndzh.com.' AND history_type = '-';\n"
        )
        f.write(
            "DELETE FROM datatracker.review_historicalreviewassignment WHERE "
            "id IN ({}) AND history_type = '-';\n".format(
                ", ".join(map(str, DELETED_REVIEWASSIGNMENTS))
            )
        )
        f.write(
            "DELETE FROM datatracker.review_historicalreviewrequest WHERE "
            "id IN ({}) AND history_type = '-';\n".format(
                ", ".join(map(str, DELETED_REVIEWREQUESTS))
            )
        )

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_recovery.py <source_file> <target_file>")
        sys.exit(1)
    
    source_file = sys.argv[1]
    target_file = sys.argv[2]
    main(source_file, target_file)
