class GroupFeatures(object):
    """Configuration of group pages and processes to have this collected
    in one place rather than scattered over the group page views."""

    has_milestones = False
    has_chartering_process = False
    has_documents = False # i.e. drafts/RFCs
    has_materials = False
    has_reviews = False
    customize_workflow = False
    about_page = "group_about"
    default_tab = about_page
    material_types = ["slides"]
    admin_roles = ["chair"]

    def __init__(self, group):
        if group.type_id in ("wg", "rg"):
            self.has_milestones = True
            self.has_chartering_process = True
            self.has_documents = True
            self.customize_workflow = True
            self.default_tab = "group_docs"
        elif group.type_id in ("team",):
            self.has_materials = True
            self.default_tab = "group_about"

        if self.has_chartering_process:
            self.about_page = "group_charter"

        from ietf.review.utils import active_review_teams
        if group in active_review_teams():
            self.has_reviews = True
            import ietf.group.views
            self.default_tab = ietf.group.views_review.review_requests

        if group.type_id == "dir":
            self.admin_roles = ["chair", "secr"]
