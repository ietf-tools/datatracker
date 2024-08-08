from django.urls import reverse as urlreverse, resolve as urlresolve, Resolver404

def _parse_return_to_path(return_to_path, default_return_to_path, allowed_path_handlers):
    if return_to_path is None:
        return_to_path = default_return_to_path

    # we need to ensure return_to_path isn't used for attacks (eg phishing).
    # return_to_url can be used in HttpResponseRedirect() which could redirect to Datatracker or offsite.
    # Eg http://datatracker.ietf.org/?ballot_edit_return_point=https://example.com/phish
    # offsite links could be phishing attempts so let's reject them all, and require valid Datatracker
    # routes
    try:
        # urlresolve will throw if the url doesn't match a route known to Django
        match = urlresolve(return_to_path)                
        # further restrict by whether it's in the list of valid routes to prevent
        # (eg) redirecting to logout
        if match.url_name not in allowed_path_handlers:
            raise ValueError(f"Invalid return_to_path not among valid matches: {match.url_name} not in {allowed_path_handlers}")
        pass
    except Resolver404:
        raise ValueError(f"Invalid ballot_edit_return_point doesn't match a route: {return_to_path}")

    return return_to_path

def parse_ballot_edit_return_point(ballot_edit_return_point: str, doc_name: str, ballot_id: str):
    default_return_to_url = urlreverse("ietf.doc.views_doc.document_ballot", kwargs=dict(name=doc_name, ballot_id=ballot_id))
    allowed_path_handlers = {
        "ietf.doc.views_doc.document_ballot",
        "ietf.doc.views_doc.document_irsg_ballot",
        "ietf.doc.views_doc.document_rsab_ballot",
        "ietf.iesg.views.agenda",
        "ietf.iesg.views.agenda_documents",
    }
    return _parse_return_to_path(ballot_edit_return_point, default_return_to_url, allowed_path_handlers)
