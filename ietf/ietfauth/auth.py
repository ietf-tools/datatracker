# Portions Copyright (C) 2009 Nokia Corporation and/or its subsidiary(-ies).
# All rights reserved. Contact: Pasi Eronen <pasi.eronen@nokia.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#
#  * Neither the name of the Nokia Corporation and/or its
#    subsidiary(-ies) nor the names of its contributors may be used
#    to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# Copyright The IETF Trust 2007, All Rights Reserved

from django.contrib.auth.backends import RemoteUserBackend
from django.contrib.auth.models import Group
from ietf.idtracker.models import IESGLogin, Role, PersonOrOrgInfo
from ietf.ietfauth.models import IetfUserProfile

from ietf.utils import log

class IetfUserBackend(RemoteUserBackend):

    def find_groups(username):
        """
        Role/Group:
        Area_Director          currently sitting AD
        IETF_Chair             currently sitting IETF Chair
        IAB_Chair              currently sitting IAB Chair
        IRTF_Chair             currently sitting IRTF Chair
        Secretariat            secretariat staff

        Roles/Groups NOT YET IMPLEMENTED
        WG_Chair               currently sitting chair of some WG
        IESG_Liaison           non-ADs on iesg@ietf.org and telechats
        Session_Chair          chairing a non-WG session in IETF meeting
        Ex_Area_Director       past AD
        """
        groups = []
        try:
            login = IESGLogin.objects.get(login_name=username)
            if login.user_level == 1:
                groups.append("Area_Director")
            elif login.user_level == 0:
                groups.append("Secretariat")
            try:
                person = login.person
                for role in person.role_set.all():
                    if role.id == Role.IETF_CHAIR:
                        groups.append("IETF_Chair")
                    elif role.id == Role.IAB_CHAIR:
                        groups.append("IAB_Chair")
                    elif role.id == Role.IRTF_CHAIR:
                        groups.append("IRTF_Chair")
            except PersonOrOrgInfo.DoesNotExist:
                pass
        except IESGLogin.DoesNotExist:
            pass
        #
        # Additional sources of group memberships: 
        # - wg_password table 
        # - other Roles 
        # - the /etc/.../*.perms files
        return groups

    find_groups = staticmethod(find_groups)

    def authenticate(self, remote_user):
        user = RemoteUserBackend.authenticate(self, remote_user)
        if not user:
            return user

        # Create profile if it doesn't exist
        try:
            profile = user.get_profile()
        except IetfUserProfile.DoesNotExist:
            profile = IetfUserProfile(user=user)
            profile.save()

        # Update group memberships
        group_names = IetfUserBackend.find_groups(user.username)
        groups = []
        for group_name in group_names:
            # Create groups as needed
            group,created = Group.objects.get_or_create(name=group_name)
            if created:
                log("IetfUserBackend created Group '%s'" % (group_name,))
            groups.append(group)
        user.groups = groups
        return user

