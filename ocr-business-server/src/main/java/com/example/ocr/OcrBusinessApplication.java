package com.example.ocr;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

@EnableAsync
@SpringBootApplication
public class OcrBusinessApplication {
    public static void main(String[] args) {
        SpringApplication.run(OcrBusinessApplication.class, args);
    }
}
