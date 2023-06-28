# Copyright The IETF Trust 2023, All Rights Reserved

from pathlib import Path

from django.http import FileResponse, Http404
from django.views.decorators.cache import cache_control
from django.shortcuts import get_object_or_404

from ietf.doc.models import Document

@cache_control(max_age=3600)
def serve_pdf(self, name, rev=None):
    doc = get_object_or_404(Document, name=name)
    if rev is None:
        rev = doc.rev
    p = Path(doc.get_file_path()).joinpath(f"{doc.name}-{rev}.pdf")
    if not p.exists():
        raise Http404
    else:
        return FileResponse(p.open(mode="rb"),content_type="application/pdf")
