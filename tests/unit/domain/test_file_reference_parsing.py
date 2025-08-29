"""Test FileReference URL parsing, path traversal, and storage patterns."""

import pytest
from domain.value_objects import FileReference


class TestFileReferenceParsing:
    """Test FileReference with various URL formats and security concerns."""
    
    def test_http_url_extracts_key_ignoring_query_and_fragment(self):
        """FileReference should extract key from HTTP URL ignoring query/fragment."""
        fr = FileReference("https://cdn.example.com/path/to/file.csv?x=1#frag")
        assert fr.get_key() == "path/to/file.csv"
        assert fr.get_scheme() == "https"
        assert fr.get_host() == "cdn.example.com"
    
    def test_s3_url_extracts_bucket_and_key(self):
        """FileReference should parse S3 URLs correctly."""
        fr = FileReference("s3://bucket-a/uploads/in.csv")
        assert fr.get_bucket() == "bucket-a"
        assert fr.get_key() == "uploads/in.csv"
        assert fr.get_scheme() == "s3"
    
    def test_s3_url_with_deep_path(self):
        """FileReference should handle deep S3 paths."""
        fr = FileReference("s3://my-bucket/tenant/t_123/jobs/2024/01/file.csv")
        assert fr.get_bucket() == "my-bucket"
        assert fr.get_key() == "tenant/t_123/jobs/2024/01/file.csv"
    
    def test_plain_bucket_key_format(self):
        """FileReference should parse plain bucket/key format."""
        fr = FileReference("mybucket/folder/file.csv")
        assert fr.get_bucket() == "mybucket"
        assert fr.get_key() == "folder/file.csv"
    
    def test_rejects_path_traversal_s3(self):
        """FileReference should reject path traversal in S3 URLs."""
        with pytest.raises(ValueError):
            FileReference("s3://bucket/../../etc/passwd")
        
        with pytest.raises(ValueError):
            FileReference("s3://bucket/../../../root/.ssh/id_rsa")
        
        with pytest.raises(ValueError):
            FileReference("s3://bucket/valid/../../../etc/shadow")
    
    def test_rejects_path_traversal_http(self):
        """FileReference should reject path traversal in HTTP URLs."""
        with pytest.raises(ValueError):
            FileReference("https://cdn.com/files/../../etc/passwd")
        
        with pytest.raises(ValueError):
            FileReference("http://example.com/../../../etc/hosts")
    
    def test_rejects_path_traversal_plain(self):
        """FileReference should reject path traversal in plain paths."""
        with pytest.raises(ValueError):
            FileReference("bucket/../../../etc/passwd")
        
        with pytest.raises(ValueError):
            FileReference("../../../etc/passwd")
        
        with pytest.raises(ValueError):
            FileReference("bucket/valid/../../../../../../etc/passwd")
    
    def test_rejects_windows_path_traversal(self):
        """FileReference should reject Windows-style path traversal."""
        with pytest.raises(ValueError):
            FileReference("s3://bucket/..\\..\\windows\\system32\\config\\sam")
        
        with pytest.raises(ValueError):
            FileReference("bucket\\..\\..\\..\\windows\\system.ini")
    
    def test_accepts_valid_csv_extensions(self):
        """FileReference should accept various CSV file extensions."""
        valid_refs = [
            "s3://bucket/file.csv",
            "s3://bucket/file.CSV",
            "s3://bucket/file.tsv",
            "s3://bucket/file.txt",
            "https://cdn.com/export.csv",
            "bucket/uploads/data.csv",
        ]
        
        for ref in valid_refs:
            fr = FileReference(ref)
            assert fr.get_key().endswith((".csv", ".CSV", ".tsv", ".txt"))
    
    def test_preserves_url_encoded_characters(self):
        """FileReference should handle URL-encoded characters properly."""
        fr = FileReference("s3://bucket/files/my%20file%20with%20spaces.csv")
        # Should either preserve encoding or decode properly
        key = fr.get_key()
        assert "my" in key and "file" in key and "spaces.csv" in key
    
    def test_handles_special_s3_characters(self):
        """FileReference should handle S3-allowed special characters."""
        # S3 allows these special chars: !-_.*'()
        fr = FileReference("s3://bucket/valid-file_name.2024(1).csv")
        assert "valid-file_name.2024(1).csv" in fr.get_key()
    
    def test_rejects_invalid_s3_bucket_names(self):
        """FileReference should reject invalid S3 bucket names."""
        invalid_buckets = [
            "s3://",  # No bucket
            "s3://bucket..name/file.csv",  # Double dots
            "s3://bucket./file.csv",  # Ends with dot
            "s3://.bucket/file.csv",  # Starts with dot
            "s3://bucket_/file.csv",  # Underscore at end
            "s3://BUCKET/file.csv",  # Uppercase (S3 requires lowercase)
            "s3://bu/file.csv",  # Too short (min 3 chars)
            "s3://" + "a" * 64 + "/file.csv",  # Too long (max 63 chars)
        ]
        
        for invalid in invalid_buckets:
            with pytest.raises(ValueError):
                FileReference(invalid)
    
    def test_rejects_non_csv_files(self):
        """FileReference should reject non-CSV file types."""
        non_csv_files = [
            "s3://bucket/file.exe",
            "s3://bucket/file.zip", 
            "s3://bucket/file.pdf",
            "https://example.com/file.doc",
            "bucket/file.json",
        ]
        
        for non_csv in non_csv_files:
            with pytest.raises(ValueError):
                FileReference(non_csv)
    
    def test_normalizes_multiple_slashes(self):
        """FileReference should normalize multiple slashes in path."""
        fr = FileReference("s3://bucket//path///to////file.csv")
        assert "//" not in fr.get_key()
        assert "///" not in fr.get_key()
    
    def test_rejects_empty_components(self):
        """FileReference should reject empty URL components."""
        with pytest.raises(ValueError):
            FileReference("")  # Empty
        
        with pytest.raises(ValueError):
            FileReference("s3:///file.csv")  # No bucket
        
        with pytest.raises(ValueError):
            FileReference("s3://bucket/")  # No file
        
        with pytest.raises(ValueError):
            FileReference("https:///file.csv")  # No host