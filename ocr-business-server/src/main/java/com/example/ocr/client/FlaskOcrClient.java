package com.example.ocr.client;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;

import java.nio.file.Path;

@Component
public class FlaskOcrClient {
    private final RestClient restClient;

    public FlaskOcrClient(
            RestClient.Builder builder,
            @Value("${app.flask-base-url:http://127.0.0.1:5001}") String baseUrl
    ) {
        this.restClient = builder.baseUrl(baseUrl).build();
    }

    public String recognize(Path file, String mode) {
        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", new FileSystemResource(file));
        body.add("mode", mode);
        String response = restClient.post()
                .uri("/internal/ocr")
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(body)
                .retrieve()
                .body(String.class);
        if (response == null || response.isBlank()) {
            throw new IllegalStateException("Flask OCR服务返回空结果");
        }
        return response;
    }
}
