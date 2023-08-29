# Copyright The IETF Trust 2023, All Rights Reserved

import json

from django.http import JsonResponse

from .models import RpcPerson

def rpc_person(request):
    
    response = []
    for rpc_person in RpcPerson.objects.all():
        capabilities = []
        for capability in rpc_person.capable_of.all():
            capabilities.append(
                dict(
                    id=capability.pk,
                    name=capability.name
                )
            )
        roles = []
        for role in rpc_person.can_hold_role.all():
            roles.append(
                dict(
                    id=role.pk,
                    name=role.name
                )
            )

        response.append(
            dict(
                id=rpc_person.pk,
                name=rpc_person.person.ascii_name(),
                capabilities = capabilities,
                roles = roles
            )
        )

    return JsonResponse(response, safe=False)
