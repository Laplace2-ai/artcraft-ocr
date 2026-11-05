Recognition weights. Not committed — the build fetches them and verifies checksums.

Expected here at build time:

    chinese_cht_PP-OCRv3_rec_mobile.onnx      traditional Chinese
    ch_PP-OCRv3_det_infer.onnx                detection        (bundled with rapidocr)
    ch_PP-OCRv3_rec_infer.onnx                simplified       (bundled with rapidocr)
    ch_ppocr_mobile_v2.0_cls_infer.onnx       orientation      (bundled with rapidocr)

Checksums are in DOCS/LICENSES.md section 5. Verify before packaging: a wrong or
missing weight shows up as garbled text, not as an error, which is the worst kind
of failure to debug after release.

Only the traditional weight has to be placed here; the other three ship inside the
rapidocr wheel and are used from there.
