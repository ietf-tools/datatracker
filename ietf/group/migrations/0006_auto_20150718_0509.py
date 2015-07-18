# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

def add_area_descriptions(apps, schema_editor):
	Group = apps.get_model("group","Group")
	Group.objects.filter(acronym='gen').update(description="""The General Area consists of a few IETF WGs and other activities focused on supporting, updating and maintaining the IETF standards development process. As General AD, the IETF Chair manages the General Area Review Team (Gen-ART) and other IETF-wide directorates.""")

	Group.objects.filter(acronym='int').update(description="""The primary technical topics covered by the Internet Area include IP layer (both IPv4 and IPv6), implications of IPv4 address depletion, co-existence between the IP versions, DNS, DHCP, host and router configuration, mobility, multihoming, identifier-locator separation, VPNs and pseudowires along with related MPLS issues, and various link layer technologies. The Internet Area is also responsible for specifying how IP will run over new link layer protocols.""")

	Group.objects.filter(acronym='ops').update(description="""The primary technical areas covered by the Operations & Management (OPS) Area include: Network Management, AAA, and various operational issues facing the Internet such as DNS operations, IPv6 operations, operational security and Routing operations.

Unlike most IETF areas, the Operations & Management area is logically divided into two separate functions: Network Management and Operations.

The Network Management function covers Internet management and AAA, and the related protocols, including but not limited to NETCONF, SNMP, RADIUS, Diameter, and CAPWAP, and of data modeling and data modeling languages used in management such as SMI and YANG. Another important role of the Management function is to identify potential or actual management issues regarding IETF protocols and documents in all areas, and to work with the other areas to resolve those issues.

The Operations function is largely responsible for soliciting operator feedback and input regarding IETF work. Another important role of the Operations function is to identify potential or actual operational issues regarding IETF protocols and documents in all areas, and to work with the other areas to resolve those issues.

The OPS area intersects most often with the Routing, Internet and Security areas.""")

	Group.objects.filter(acronym='rtg').update(description="""The Routing Area is responsible for ensuring continuous operation of the Internet routing system by maintaining the scalability and stability characteristics of the existing routing protocols, as well as developing new protocols, extensions, and bug fixes in a timely manner. Forwarding methods (such as destination-based unicast and multicast forwarding, MPLS, and pseudowire) as well as associated routing and signalling protocols (such as OSPF, IS-IS, BGP, RSVP-TE, LDP, PIM, L1-, L2-, and L3-VPNs) are within the scope of the Routing Area. Traffic engineering routing and signaling protocols are in scope, as is the architecture and protocols for the Path Computation Element that helps to select end-to-end paths for traffic-engineered routing. The Routing Area also works on Generalized MPLS used in the control plane of optical networks as well as security aspects of the routing system. The Routing Area has recently developed a routing protocol (RPL) for use in low-powered and lossy networks.

The Routing Area intersects most frequently with the Internet Area, the Operations & Management Area, and the Security Area. Interaction with the Internet Area concentrates mainly on IP Forwarding and Multicast. With the Operations & Management Area the focus is on MIB development. With the Security area the focus is on routing protocol security.

Current work in the Routing Area has some overlap with work in other SDOs, in particular interactions with the ITU-T on MPLS-TP.""")

	Group.objects.filter(acronym='sec').update(description="""The Security Area is the home for working groups focused on security protocols. They provide one or more of the security services: integrity, authentication, non-repudiation, confidentiality, and access control. Since many of the security mechanisms needed to provide these security services employ cryptography, key management is also vital.

The Security Area intersects with all other IETF Areas, and the participants are frequently involved with activities in the working groups from other areas. This involvement focuses upon practical application of Security Area protocols and technologies to the protocols of other Areas.""")

	Group.objects.filter(acronym='tsv').update(description="""The transport and services area - usually just called "transport area" or "TSV area" - covers a range of technical topics related to data transport in the Internet.

The Transport Area works on mechanisms related to end-to-end data transport to support Internet applications and services that exchange potentially large volumes of traffic at potentially high bandwidths. A key focus are mechanisms to detect and react to congestion in the Internet, such as the congestion control algorithms in Internet transport control protocols such as TCP, SCTP, and DCCP, as well as congestion management schemes such as PCN and CONEX.

Current and new transport work includes congestion signaling and reporting, forward error correction, multicast, QoS and reservation signaling, DiffServ? and congestion control for unresponsive flows, NAT regularization and specification, storage protocols for the Internet, peer-to-peer streaming, performance metrics for Internet paths, experimentation with congestion control schemes developed in the IRTF, multipath extensions to existing transport protocols, congestion control for "background" bulk transfers, and extensions to the IETF protocols for multimedia transport.

The transport area intersects most frequently with Internet area, the applications area, the RAI area, the security area and several IRTF research groups.""")

	Group.objects.filter(acronym='art').update(description="""The ART area develops application protocols and architectures in the IETF. The work in the area falls into roughly three categories, with blurry distinctions between them. One category consists of protocols and architectures specifically designed to support delay-sensitive interpersonal communications via voice, video, instant messaging, presence, and other means, otherwise known as "real-time" applications and services. A second category consists of protocols and architectures to support applications that may be more tolerant of delay, including HTTP, email, and FTP. The third category consists of building blocks that are designed for use across a wide variety of applications and may be employed by both real-time and non-real-time applications, such as URI schemes, MIME types, authentication mechanisms, data formats, metrics, and codecs.""")
 

class Migration(migrations.Migration):

    dependencies = [
        ('group', '0005_auto_20150504_0726'),
    ]

    operations = [
		migrations.RunPython(add_area_descriptions)
    ]
