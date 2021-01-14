# Renewing SSL cert for LIMS servers

All certificates have to be renewed yearly. All LIMS servers use certs from UiO.  [Even though we have a certification authority in FreeIPA which supports auto-renewal, we can't use the certs, because some parts of Clarity require globally trusted certificates and has separate trusted root CA database.]

## Procedure

The procedure is done in two steps. The first step is to submit a request to UiO. The second step should be done after receiving a .crt from UiO, and entails configuring the LIMS to use the new cert.

### Step 1 -- Generate key and submit CSR

Log on to the LIMS server, open a root shell, and go to root's home dir (/root). Create a subdirectory with the date, and go into it.

Follow the instructions in UiO's Cookbook up to and including key and CSR generation.  https://www.uio.no/tjenester/it/sikkerhet/sertifikater/kokebok.html Example:

    openssl req -new -config sandbox-lims.sequencing.uio.no.cnf -keyout sandbox-lims.sequencing.uio.no.key -out sandbox-lims.sequencing.uio.no.csr

We don't need to encrypt the key because we run this as the root user on the host that's going to use the cert. Root is anyway going to have easy access to the key contents. So after generating the key, you can continue to the Nettskjema (bestillingsskjema). Paste the content of the csr (``cat *.csr``). The CSR contains all the information about the certificate (hostname, etc) in an encoded form. Enter as the contact email: clarity-lims-it@sequencing.uio.no.

### Step 2 -- Configure usage of the new certificate

