from rest_framework import serializers
from .models import Role, User, AppConfig, Conversation, Fact
import uuid


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'level', 'capabilities', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    role_id = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ['id', 'phone', 'email', 'role', 'role_id', 'metadata', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        role_id = validated_data.pop('role_id', None)
        if role_id:
            try:
                role = Role.objects.get(id=role_id)
                validated_data['role'] = role
            except Role.DoesNotExist:
                raise serializers.ValidationError({'role_id': 'Role no encontrado'})
        return super().create(validated_data)


class AppConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppConfig
        fields = ['id', 'name', 'level', 'capabilities', 'is_active', 'config', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class ConversationSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True, required=False)
    app = AppConfigSerializer(read_only=True)
    app_id = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Conversation
        fields = [
            'id', 'session_id', 'user', 'user_id', 'app', 'app_id', 
            'messages', 'metadata', 'is_active', 'created_at', 'updated_at', 'last_message_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_message_at']


class FactSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True, required=False)
    source_conversation = ConversationSerializer(read_only=True)
    source_conversation_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = Fact
        fields = [
            'id', 'subject', 'relation', 'object', 'confidence', 
            'user', 'user_id', 'source_conversation', 'source_conversation_id',
            'metadata', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ChatMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['user', 'assistant', 'system'])
    content = serializers.CharField()
    timestamp = serializers.DateTimeField(required=False, allow_null=True)


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(required=True)
    session_id = serializers.CharField(required=False, allow_null=True)
    user_id = serializers.UUIDField(required=False, allow_null=True)
    phone = serializers.CharField(required=False, allow_null=True)
    email = serializers.EmailField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False, default=dict)

    def validate(self, data):
        # Al menos uno de user_id, phone o email debe estar presente
        if not any([data.get('user_id'), data.get('phone'), data.get('email')]):
            raise serializers.ValidationError(
                "Debe proporcionar al menos uno de: user_id, phone o email"
            )
        return data


class ChatResponseSerializer(serializers.Serializer):
    response = serializers.CharField()
    session_id = serializers.CharField()
    user_id = serializers.UUIDField()
    conversation_id = serializers.UUIDField()
    timestamp = serializers.DateTimeField()