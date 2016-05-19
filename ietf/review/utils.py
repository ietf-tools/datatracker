from ietf.group.models import Group

def active_review_teams():
    # if there's a ReviewResultName defined, it's a review team
    return Group.objects.filter(state="active").exclude(reviewresultname=None)
    
