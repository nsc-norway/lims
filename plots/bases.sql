SELECT
	process.daterun,
    SUM(CAST(artifact_udf_view.udfvalue AS FLOAT)),
    process.processtype

FROM processtype, process, processiotracker, artifact, artifact_udf_view, artifactstate
WHERE
	(
        processtype.displayname='Illumina Sequencing (HiSeq X) 1.0' OR
        processtype.displayname='Illumina Sequencing (HiSeq 3000/4000) 1.0' OR
        processtype.displayname='Illumina Sequencing (Illumina SBS) 5.0' OR
        processtype.displayname='NextSeq Run (NextSeq) 1.0' OR
        processtype.displayname='MiSeq Run (MiSeq) 5.0'
    ) AND
    process.typeid=processtype.typeid AND
	processiotracker.processid=process.processid AND
	artifact.artifactid=processiotracker.inputartifactid AND
	artifact_udf_view.artifactid=artifact.artifactid AND
    (
        artifact_udf_view.udfname IN ('Yield PF (Gb) R1', 'Yield PF (Gb) R2')
    ) AND
	artifactstate.artifactid=artifact.artifactid AND
	artifactstate.qcflag = 1 AND
    process.daterun IS NOT NULL AND
    artifact_udf_view.udfvalue IS NOT NULL AND
    YEAR(process.daterun) >= 2016
    
	GROUP BY process.daterun
    ORDER BY process.daterun

