# Renewing SSL cert for LIMS servers

All certificates have to be renewed yearly. All LIMS servers use certs from UiO.  [Even though we have a certification authority in FreeIPA which supports auto-renewal, we can't use the certs, because some parts of Clarity require globally trusted certificates and has separate trusted root CA database.]

## Procedure

The procedure is done in two steps. The first step is to submit a request to UiO. The second step should be done after receiving a .crt from UiO, and entails configuring the LIMS to use the new cert.

### Step 1 -- Generate key and submit CSR

Log on to the LIMS server, open a root shell, and go to root's home dir (/root). Create a subdirectory with the date, and go into it.

Follow the instructions in UiO's Cookbook up to and including key and CSR generation.  https://www.uio.no/tjenester/it/sikkerhet/sertifikater/kokebok.html Example:

    openssl req -new -config sandbox-lims.sequencing.uio.no.cnf -keyout sandbox-lims.sequencing.uio.no.key -out sandbox-lims.sequencing.uio.no.csr

We don't need to encrypt the key because we run this as the root user on the host that's going to use the cert. Root is anyway going to have easy access to the key contents. So after generating the key, you can continue to the Nettskjema (bestillingsskjema). Paste the content of the csr (``cat *.csr``). The CSR contains all the information about the certificate (hostname, etc) in an encoded form. It does not contain confidential information. Enter as the contact email: clarity-lims-it@sequencing.uio.no.

### Step 2 -- Configure usage of the new certificate

You receive a zip file with contents including this:

* (hostname).crt
* intermediate.crt

These are the certificate files. They are not confidential.

Transfer the two crt files to the LIMS server. Put a copy in /root/yyyy-mm, as a backup.

This is the procedure for Clarity LIMS.

https://genologics.zendesk.com/hc/en-us/articles/360024942552-Installing-a-Purchased-SSL-TLS-Certificate


For us, it means going to /opt/gls/clarity/config/ and running as root: `bash installCertificates.sh`. Enter the key and cert, and for the chain file enter intermediate.crt.


Stop and start Clarity:

    /opt/gls/clarity/bin/run_clarity.sh stop
    /opt/gls/clarity/bin/run_clarity.sh stort


