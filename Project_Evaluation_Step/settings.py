import sys
import re
from genologics.lims import *
from genologics import config


project_fields = [
        "Project type",
        "Reference genome",
        "Desired insert size",
        "Sample prep requested",
        "Bioinformatic services",
        "Contact person",
        "Contact institution",
        "Contact address",
        "Contact email",
        "Contact telephone",
        "Billing contact person",
        "Billing address",
        "Billing email",
        "Billing telephone",
        "Purchase order number",
        "Kontostreng (Internal orders only)",
        "Delivery method",
        "Funded by Norsk Forskningsradet",
        "Billing institution",
        "Sequencing method",
        "Sample type",
	"Sample buffer",
        "Species",
	"Method used to determine concentration",
	"Method used to purify DNA/RNA",
        "Sequencing instrument requested",
        "Read length requested",
        "Project comments",
        "Project goal",
        "NeLS project identifier",
        "REK approval number",
        "Total # of lanes requested",
        "Date samples received",
        "Total # of tubes received",
        "Storage location",
        "QC upon receipt: BioAnalyzer",
        "QC upon receipt: Nanodrop",
        "QC upon receipt: Qubit",
        "QC upon receipt: SYBR qPCR",
        "QC upon receipt: None - Proceed to prep",
        "QC upon receipt: comments",
        "Quoted price (NOK)",
        "Billing comments",
        "Evaluation type",
        "Evaluation comments",
        "Library prep used",
        "Prepaid account",
        "Number of lanes",
        "Test project"
]

email_fields = ['Contact email', 'Billing email']

multiline_to_single_line = {
        "Evaluation comments": "Evaluation comments_S",
        "Billing comments": "Billing comments_S",
        "Project comments": "Project comments_S",
        "Project goal": "Project goal_S",
        "Billing address": "Billing address_S",
        "Contact address": "Contact address_S",
        }

