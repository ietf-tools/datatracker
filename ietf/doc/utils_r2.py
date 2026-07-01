# Copyright The IETF Trust 2026, All Rights Reserved

from django.core.files.storage import storages

from ietf.doc.models import StoredObject


def rfcs_are_in_r2(rfc_number_list=()):
    r2_rfc_bucket = storages["r2-rfc"]
    for rfc_number in rfc_number_list:
        stored_objects = StoredObject.objects.filter(
            store="rfc", doc_name=f"rfc{rfc_number}"
        )
        for stored_object in stored_objects:
            if not r2_rfc_bucket.exists(stored_object.name):
                return False
    return True
