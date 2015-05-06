#### Print reagent labels (this code could be expanded to other print jobs)

### Edit these process types for adding reagents

  - Adenylate ends & Ligate Adapters (TruSeq RNA) 5.0

### Make these changes to the process types

  - In external programs, check the box and add a program
   - Channel name: limsserver
   - Name: Print index table
   - Command line call: /usr/bin/python /opt/gls/clarity/customextensions/lims/printout/reagent-list.py {processLuid}

### Changes to 

