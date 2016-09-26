SELECT
	MAX(process.daterun)

FROM processtype, process, processiotracker, artifact, artifact_sample_map, sample, project, process_udf_view, artifact_udf_view, artifactstate
WHERE
	(
        processtype.displayname='Illumina Sequencing (Illumina SBS) 5.0' OR
        processtype.displayname='Illumina Sequencing (HiSeq 3000/4000) 1.0'
    ) AND
	process.typeid=processtype.typeid AND
	processiotracker.processid=process.processid AND
	artifact.artifactid=processiotracker.inputartifactid AND
	artifact_udf_view.artifactid=artifact.artifactid AND
	process_udf_view.processid=process.processid AND
	artifact_sample_map.artifactid=artifact.artifactid AND
	artifact_sample_map.processid=sample.processid AND
	project.projectid=sample.projectid AND
	artifactstate.artifactid=artifact.artifactid AND
	artifactstate.qcflag = 1 AND
	process.daterun IS NOT NULL AND
    
	--- EXOME
	project.name ILIKE 'Diag-excap%'
	--project.name ILIKE '%'

	GROUP BY sample.name

