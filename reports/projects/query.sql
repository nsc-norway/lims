
SELECT 
	process_udf_view.udfvalue AS "Run ID",
	(containerplacement.wellyposition + 1),
	artifact.name,
	CASE
		WHEN (artifactstate.qcflag = 0) THEN 'None'
		WHEN (artifactstate.qcflag = 1) THEN 'PASS'
		WHEN (artifactstate.qcflag = 0) THEN 'FAIL'
	END
FROM processtype, process, processiotracker, artifact, process_udf_view, artifactstate, containerplacement
WHERE
	processtype.displayname='Illumina Sequencing (Illumina SBS) 5.0' AND
	process.typeid=processtype.typeid AND
	processiotracker.processid=process.processid AND
	artifact.artifactid=processiotracker.inputartifactid AND
	process_udf_view.processid=process.processid AND
	artifactstate.artifactid=artifact.artifactid AND
	containerplacement.processartifactid=artifact.artifactid AND
	process_udf_view.udfname='Run ID' AND
	(SELECT project.name
		from project, sample, artifact_sample_map WHERE 
		project.projectid = sample.projectid AND
		artifact_sample_map.processid = sample.processid AND
		artifact_sample_map.artifactid = artifact.artifactid
		LIMIT 1) = %s

	ORDER BY process_udf_view.udfvalue, containerplacement.wellyposition

