
SELECT 
	artifactstate.*
	/*process_udf_view.udfvalue AS "Run ID",
	(containerplacement.wellyposition + 1),
	artifact.name,
	CASE
		WHEN (artifactstate.qcflag = 0) THEN 'None'
		WHEN (artifactstate.qcflag = 1) THEN 'PASS'
		WHEN (artifactstate.qcflag = 0) THEN 'FAIL'
	END*/
FROM processtype, process, processiotracker, artifact, artifact_sample_map, sample, project, process_udf_view, artifactstate, containerplacement
WHERE
	project.name='Sun-excap1-2015-02-23' AND
	processtype.displayname='Illumina Sequencing (Illumina SBS) 5.0' AND
	process.typeid=processtype.typeid AND
	processiotracker.processid=process.processid AND
	artifact.artifactid=processiotracker.inputartifactid AND
	process_udf_view.processid=process.processid AND
	artifact_sample_map.artifactid=artifact.artifactid AND
	artifact_sample_map.processid=sample.processid AND
	project.projectid=sample.projectid AND
	artifactstate.artifactid=artifact.artifactid AND
	containerplacement.processartifactid=artifact.artifactid AND
	process_udf_view.udfname='Run ID'

	ORDER BY process_udf_view.udfvalue, containerplacement.wellyposition

