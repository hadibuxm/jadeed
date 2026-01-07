from rest_framework import serializers


class VisionCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(allow_blank=True, required=False, default="")

    def validate(self, attrs):
        name = attrs.get("name", "").strip()
        if not name:
            raise serializers.ValidationError({"name": ["This field may not be blank."]})

        description = (attrs.get("description") or "").strip()
        return {"name": name, "description": description}


class PortfolioCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(allow_blank=True, required=False, default="")

    def validate(self, attrs):
        name = attrs.get("name", "").strip()
        if not name:
            raise serializers.ValidationError({"name": ["This field may not be blank."]})
        description = (attrs.get("description") or "").strip()
        return {"name": name, "description": description}


class ProductCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(allow_blank=True, required=False, default="")
    portfolio_id = serializers.IntegerField()
    github_repository_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True,
        required=False,
        default=list,
    )

    def validate(self, attrs):
        name = attrs.get("name", "").strip()
        if not name:
            raise serializers.ValidationError({"name": ["This field may not be blank."]})
        description = (attrs.get("description") or "").strip()
        repo_ids = attrs.get("github_repository_ids") or []
        return {
            "name": name,
            "description": description,
            "portfolio_id": attrs.get("portfolio_id"),
            "github_repository_ids": repo_ids,
        }


class FeatureCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(allow_blank=True, required=False, default="")
    product_id = serializers.IntegerField()
    github_repository_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        name = attrs.get("name", "").strip()
        if not name:
            raise serializers.ValidationError({"name": ["This field may not be blank."]})
        description = (attrs.get("description") or "").strip()
        return {
            "name": name,
            "description": description,
            "product_id": attrs.get("product_id"),
            "github_repository_id": attrs.get("github_repository_id"),
        }
