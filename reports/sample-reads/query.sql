
SELECT 
	MAX(sample.name),
	SUM(CAST(artifact_udf_view.udfvalue AS integer))

FROM processtype, process, processiotracker, outputmapping, artifact, artifact inputartifact, artifact_udf_view, artifactstate, sample, artifact_sample_map, project
WHERE
	-- Process type --
	processtype.displayname='Demultiplexing and QC NSC 2.0' AND
	process.typeid=processtype.typeid AND

	-- Join artifact tables (output) --
	processiotracker.processid=process.processid AND
	outputmapping.trackerid=processiotracker.trackerid AND
	artifact.artifactid=outputmapping.outputartifactid AND

	-- Join input artifact --
	inputartifact.artifactid=processiotracker.inputartifactid AND

	-- Sample -> Project --
	artifact_sample_map.artifactid=artifact.artifactid AND
	sample.processid=artifact_sample_map.processid AND
	sample.projectid=project.projectid AND
	project.name LIKE %s AND

	-- Join UDF --
	artifact_udf_view.artifactid=artifact.artifactid AND
	artifact_udf_view.udfname='# Reads' AND

	-- QC flag on input artifact (lane) --
	artifactstate.artifactid=inputartifact.artifactid AND
	artifactstate.qcflag=1

	GROUP BY sample.sampleid

