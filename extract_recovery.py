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
    assert(len(TARGET_TABLES) == 38)
    assert(set(TARGET_TABLES) == set(tables.keys()))
    with open(target_file, "w") as f:
        for table in TARGET_TABLES:
            f.writelines(tables[table])
            f.write("\\.\n\n")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_recovery.py <source_file> <target_file>")
        sys.exit(1)
    
    source_file = sys.argv[1]
    target_file = sys.argv[2]
    main(source_file, target_file)
