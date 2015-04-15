import sys
import re
from genologics.lims import *
from genologics import config


project_fields = [
        "Project type",
        "Reference genome",
        "Desired insert size",
        "Sample prep requested",
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
        "Application",
        "Sequencing instrument requested",
        "Read length requested",
        "Project comments",
        "Project goal",
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
        "Evaluation comments"
]

sample_fields = [
        ("Sample type", "NSC sample type"),
        ("Sample buffer", "NSC sample buffer"),
        ("Method used to determine concentration", "NSC method used to determine concentration"),
        ("Method used to purify DNA/RNA", "NSC method used to purify DNA/RNA")
]



email_fields = ['Contact email', 'Billing email']


